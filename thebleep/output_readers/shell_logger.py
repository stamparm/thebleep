import json
import os
import socket
from shutil import get_terminal_size
from .. import const, logs


def _get_socket_path():
    return os.environ.get(const.SHELL_LOGGER_SOCKET_ENV)


def is_available():
    """Returns `True` if shell logger socket available.

    A socket, not merely something at that path: `os.path.exists` was happy
    with an ordinary file, and then connecting to it raised. Existing is still
    not the same as answering -- a daemon can be gone and its socket file left
    behind -- which is what `get_output` handles.

    :rtype: bool

    """
    path = _get_socket_path()
    if not path:
        return False

    import stat

    try:
        return stat.S_ISSOCK(os.stat(path).st_mode)
    except OSError:
        return False


# A local socket that a listening daemon answers from memory. A second of it is
# already a long time; anything longer is a daemon that is not going to answer,
# and waiting for it is worse than not asking. A response also gets a ceiling:
# `readline()` with no limit let a malformed daemon response grow without bound.
TIMEOUT = 1.0
MAX_RESPONSE = 8 * 1024 * 1024


def _get_last_n(n):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(TIMEOUT)
        client.connect(_get_socket_path())
        request = json.dumps({
            "type": "list",
            "count": n,
        }) + '\n'
        client.sendall(request.encode('utf-8'))
        with client.makefile('rb') as stream:
            response = stream.readline(MAX_RESPONSE + 1)
        if len(response) > MAX_RESPONSE or not response.endswith(b'\n'):
            raise ValueError('shell logger response is too large or incomplete')
        return json.loads(response.decode('utf-8'))['commands']


def _get_output_lines(output):
    # See read_log: pyte is only needed once there is a screen to render.
    import pyte

    lines = output.split('\n')
    screen = pyte.Screen(get_terminal_size().columns, len(lines))
    stream = pyte.Stream(screen)
    stream.feed('\n'.join(lines))
    return screen.display


def get_output(script):
    """Gets command output from shell logger, or `None`.

    `None` for every way this can fail to answer, because the caller falls
    through to the other readers on `None` and there is nothing here worth
    ending a correction over. Reaching a separate process over a socket has
    plenty of ways to fail: a daemon that exited and left its socket file
    behind (`ConnectionRefusedError`), one that accepts and then says nothing
    (a timeout), a reply that is not the JSON expected. Each of those used to
    come out of the middle of a correction as a traceback.

    """
    with logs.debug_time(u'Read output from external shell logger'):
        try:
            commands = _get_last_n(const.SHELL_LOGGER_LIMIT)
        except Exception:                                    # noqa: BLE001
            logs.debug(u'Shell logger did not answer; using another reader')
            return None

        if not isinstance(commands, list):
            return None

        for command in commands:
            # The loop used to `return None` from its `else` branch, so only
            # the *newest* logged command was ever considered -- correcting
            # anything else silently reported that no output was available,
            # which switches off every rule that needs it.
            if not isinstance(command, dict):
                continue
            if command.get('command') != script:
                continue

            try:
                lines = _get_output_lines(command.get('output') or '')
            except Exception:                                # noqa: BLE001
                logs.debug(u'Shell logger output could not be rendered')
                return None
            return '\n'.join(lines).strip()

        logs.warn("Output isn't available in shell logger")
        return None
