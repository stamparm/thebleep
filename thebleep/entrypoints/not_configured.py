# Initialize output before importing any module, that can use colorama.
from ..system import init_output

init_output()

import getpass  # noqa: E402
import os  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from psutil import Process  # noqa: E402
from .. import logs, const  # noqa: E402
from ..shells import shell  # noqa: E402
from ..conf import settings  # noqa: E402
from ..system import expanduser  # noqa: E402


def _get_shell_pid():
    """Returns parent process pid, or `None` when it cannot be asked."""
    try:
        proc = Process(os.getpid())
    except Exception:                                        # noqa: BLE001
        # `psutil` raising here means there is no parent to find. The sibling
        # shell walk in `shells.generic` already guards this; this did not, and
        # a tracker keyed on `None` simply never matches.
        return None

    try:
        try:
            return proc.parent().pid
        except TypeError:
            return proc.parent.pid
    except Exception:                                        # noqa: BLE001
        return None


def _get_not_configured_usage_tracker_path():
    """Where the pid of the shell that ran `bleep` first is remembered.

    Under the user's own cache directory rather than a predictable name in a
    shared `/tmp`. The old path was `/tmp/thebleep.last_not_configured_run_<me>`
    opened `'w'`, which followed a symlink anybody could have planted and
    truncated whatever it pointed at; a plain file planted there was enough to
    break the first run for good.

    `$XDG_RUNTIME_DIR` would be the textbook home for something this transient,
    but it does not exist on macOS or Windows, and the cache directory is
    already where this program keeps state it can afford to lose.

    """
    from .. import cachefile

    return cachefile.directory().joinpath(u'not-configured-run-{}'.format(
        getpass.getuser(),
    ))


def _record_first_run():
    """Records shell pid to tracker file.

    Best-effort: a cache directory that cannot be written to is a reason to
    show the instructions twice, not to fail.

    """
    info = {'pid': _get_shell_pid(),
            'time': time.time()}

    path = _get_not_configured_usage_tracker_path()
    try:
        _mkdir(path.parent)
        # `O_NOFOLLOW` so a symlink is refused rather than followed, and 0600
        # because the pid of the user's shell is nobody else's business.
        # `shell_logger._open_log` does the same thing for the same reason.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(
            os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
        descriptor = os.open(str(path), flags, 0o600)
        with os.fdopen(descriptor, 'w') as tracker:
            json.dump(info, tracker)
    except (OSError, IOError, ValueError):
        logs.debug(u'Could not record the first run in {}'.format(path))


def _mkdir(directory):
    try:
        os.makedirs(str(directory), mode=0o700)
    except OSError:
        if not os.path.isdir(str(directory)):
            raise


def _get_previous_command():
    history = shell.get_history()

    if history:
        return history[-1]
    else:
        return None


def _is_second_run():
    """Returns `True` when we know that `bleep` called second time."""
    tracker_path = _get_not_configured_usage_tracker_path()

    current_pid = _get_shell_pid()
    if current_pid is None:
        return False

    try:
        with tracker_path.open('r', encoding='utf-8', errors='replace') as tracker:
            info = json.load(tracker)
    except (OSError, IOError, ValueError):
        # Missing, unreadable, or not JSON: no record of a first run, so this
        # is one.
        return False

    if not (isinstance(info, dict) and info.get('pid') == current_pid):
        return False

    if _get_previous_command() == 'bleep':
        return True

    # A record with no time in it is a record this program did not write, and
    # `.get('time', 0)` made it look like a run from 1970 -- which is to say
    # one that happened an eternity ago, and therefore, after the subtraction,
    # always a recent one. Editing the shell's startup file is not something to
    # do on the strength of a file whose contents nobody recognises.
    recorded = info.get('time')
    if not isinstance(recorded, (int, float)):
        return False

    return 0 <= time.time() - recorded < const.CONFIGURATION_TIMEOUT


def _is_already_configured(configuration_details):
    """Returns `True` when alias already in shell config."""
    path = expanduser(configuration_details.path)
    with path.open('r', encoding='utf-8', errors='replace') as shell_config:
        return configuration_details.content in shell_config.read()


def _configure(configuration_details):
    """Adds alias to shell config."""
    path = expanduser(configuration_details.path)
    with path.open('a', encoding='utf-8') as shell_config:
        shell_config.write(u'\n')
        shell_config.write(configuration_details.content)
        shell_config.write(u'\n')


def main():
    """Shows useful information about how-to configure alias on a first run
    and configure automatically on a second.

    It'll be only visible when user type bleep and when alias isn't configured.

    """
    settings.init()
    configuration_details = shell.how_to_configure()
    if (
        configuration_details and
        configuration_details.can_configure_automatically
    ):
        if _is_already_configured(configuration_details):
            logs.already_configured(configuration_details)
            return
        elif _is_second_run():
            _configure(configuration_details)
            logs.configured_successfully(configuration_details)
            return
        else:
            _record_first_run()

    logs.how_to_configure_alias(configuration_details)
