# -*- encoding: utf-8 -*-

"""A warm process answering command-only corrections over a private socket.

A correction costs about sixty milliseconds, and nearly all of it is starting
Python and loading what a correction needs. That is fine once, after a
failure. It is not fine on the path `--ambient` and <kbd>Esc</kbd> <kbd>Esc</kbd>
take, which runs on a keystroke: return on a line whose first word the shell
does not know, and the answer should be there before the eye moves.

`thebleep --serve` is that process kept warm. It listens on a Unix socket in
a directory only this user can enter, answers one question per connection --
"what is the command-only correction of this line?" -- from the rule pack it
already has in memory, and exits after half an hour without a question. It
runs nothing, reads no output, keeps no state between questions beyond the
loaded rules, and answers only the shell it was started for, because a shell's
aliases and quoting are its own.

Only zsh has a socket client of its own (`zsh/net/socket`), so only zsh's
bindings use this; the others start Python as before. It is off by default:
`warm_server = True` makes the zsh bindings try the socket, and start the
server in the background when it is not there yet.

"""

import json
import os
import socket
import stat
import sys
import time

from . import logs

IDLE_SECONDS = 30 * 60
MAX_REQUEST = 256 * 1024
BACKLOG = 8

# A Unix socket path is short by law: 108 bytes on Linux, 104 on macOS and
# the BSDs, terminator included. macOS's temporary directories alone run to
# fifty, so the place is chosen with the whole path in mind.
MAX_SOCKET_PATH = 100
LONGEST_NAME = 'inline-powershell.sock'


def _fits(directory):
    return len(os.path.join(directory, LONGEST_NAME).encode(
        'utf-8', 'replace')) <= MAX_SOCKET_PATH


def socket_directory():
    """Where the socket goes.

    The runtime directory, then the cache, then a directory of this user's
    under the temporary directory -- the first whose socket path fits.

    """
    candidates = []
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if runtime and os.path.isdir(runtime):
        candidates.append(os.path.join(runtime, 'thebleep'))
    from . import cachefile

    candidates.append(os.path.join(str(cachefile.directory()), 'serve'))
    import tempfile

    who = str(os.getuid()) if hasattr(os, 'getuid') else 'user'
    candidates.append(os.path.join(tempfile.gettempdir(),
                                   'thebleep-serve-' + who))
    candidates.append(os.path.join('/tmp', 'thebleep-serve-' + who))
    for directory in candidates:
        if _fits(directory):
            return directory
    return candidates[0]


def socket_path(shell_name):
    return os.path.join(socket_directory(),
                        'inline-{}.sock'.format(shell_name))


def _private_directory(path):
    """`path`, made or checked to be a directory nobody else can enter.

    Refused when it exists but is somebody else's or more open than 0700: the
    same argument as the cache directory's, since what comes back over this
    socket is put on the user's command line.

    """
    try:
        os.makedirs(path, mode=0o700, exist_ok=True)
        info = os.lstat(path)
    except OSError:
        return None
    if not stat.S_ISDIR(info.st_mode):
        return None
    if hasattr(os, 'getuid') and info.st_uid != os.getuid():
        return None
    if info.st_mode & 0o077:
        return None
    return path


def correct(script):
    """The command-only correction of `script`, or None: what the server
    answers, and what `--inline` prints."""
    from .entrypoints.inline import correct as inline_correct

    return inline_correct(script)


def _answer(request):
    """One request as bytes -> one response as bytes."""
    try:
        payload = json.loads(request.decode('utf-8'))
        script = payload.get('script')
        aliases = payload.get('aliases')
        cwd = payload.get('cwd')
    except (ValueError, AttributeError, UnicodeDecodeError):
        # Not "no correction": a question that could not be read, which the
        # client answers by asking Python directly.
        return b'error\n'
    if not isinstance(script, str) or not script.strip():
        return b'none\n'
    if isinstance(aliases, str):
        os.environ['TB_SHELL_ALIASES'] = aliases
    else:
        os.environ.pop('TB_SHELL_ALIASES', None)
    # The rules read the project around the *client's* directory, not the
    # one the server happened to start in.
    if isinstance(cwd, str) and cwd:
        try:
            os.chdir(cwd)
        except OSError:
            return b'error\n'

    # Answers memoized for one process are answers for one question here:
    # the alias list and PATH may have changed since the last one.
    from .utils import forget_memoized

    forget_memoized()
    try:
        fixed = correct(script)
    except Exception as error:                                 # noqa: BLE001
        logs.debug(u'Server could not correct {!r}: {!r}'.format(
            script, error))
        return b'none\n'
    if fixed is None:
        return b'none\n'
    return b'ok\n' + fixed.encode('utf-8')


def _read_request(connection):
    connection.settimeout(2)
    chunks = []
    total = 0
    while True:
        try:
            chunk = connection.recv(65536)
        except (socket.timeout, OSError):
            break
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_REQUEST:
            return None
        if chunk.endswith(b'\n'):
            break
    return b''.join(chunks)


def serve(shell_name, idle=IDLE_SECONDS, ready=None):
    """Listen until `idle` seconds pass without a question. Returns an exit
    status. `ready`, when given, is called with the socket path once
    listening -- the tests wait on it."""
    if not hasattr(socket, 'AF_UNIX'):
        logs.failed('The warm server needs Unix sockets.')
        return 2
    directory = _private_directory(socket_directory())
    if directory is None:
        logs.failed('{} is not a directory only you can enter; not serving.'
                    .format(socket_directory()))
        return 2
    path = socket_path(shell_name)
    try:
        os.unlink(path)
    except OSError:
        pass

    from .conf import settings

    settings.init()
    # Warm what a correction will need, so the first question is as fast as
    # the tenth.
    correct('gti status')

    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old_umask = os.umask(0o177)
    try:
        listener.bind(path)
    except OSError as error:
        logs.failed(u'Could not listen on {}: {}'.format(path, error))
        return 2
    finally:
        os.umask(old_umask)
    listener.listen(BACKLOG)
    listener.settimeout(idle)
    if ready is not None:
        ready(path)
    logs.debug(u'Serving {} corrections on {}'.format(shell_name, path))
    try:
        while True:
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                logs.debug('Idle; leaving')
                return 0
            with connection:
                request = _read_request(connection)
                response = b'error\n' if request is None else _answer(request)
                try:
                    connection.sendall(response)
                except OSError:
                    pass
    finally:
        listener.close()
        try:
            os.unlink(path)
        except OSError:
            pass


def ask(shell_name, script, aliases=None, timeout=1.0, cwd=None):
    """A client, for tests and for a shell with no socket client of its own.
    Returns the correction, None for "no correction", or raises OSError when
    there is no server."""
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    try:
        connection.connect(socket_path(shell_name))
        connection.sendall(json.dumps({'script': script, 'aliases': aliases,
                                       'cwd': cwd or os.getcwd()})
                           .encode('utf-8') + b'\n')
        try:
            connection.shutdown(socket.SHUT_WR)
        except OSError:
            # The newline already ended the question; a server quick enough
            # to have answered and hung up makes macOS refuse the shutdown.
            pass
        chunks = []
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        connection.close()
    response = b''.join(chunks)
    status, _, body = response.partition(b'\n')
    if status == b'error':
        raise OSError('the server could not read the question')
    if status != b'ok':
        return None
    return body.decode('utf-8', 'replace')


def main(args):
    from .shells import shell

    started = time.time()
    status = serve(shell._shell_name(), getattr(args, 'serve_idle', None)
                   or IDLE_SECONDS)
    logs.debug(u'Served for {:.0f}s'.format(time.time() - started))
    sys.stdout.flush()
    return status
