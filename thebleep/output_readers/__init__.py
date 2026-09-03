"""Where the output of the command that failed comes from.

Capture uses an ordered backend chain. A correction normally uses one of them --
and in instant mode,
where the recording turns out to hold no answer, falls through from that one to
the replay path with its question intact. They used to all be
imported here, so every correction paid for all three: `shell_logger` brings in
`socket` and `json`, `rerun` brings in `subprocess` and the threading and
signal machinery underneath it, and `read_log` brings in `mmap` and `re`. On
Windows, where finding and opening a module is the dearest thing an interpreter
does, that was three readers' worth of imports to use one.

So each arrives when it is chosen. The choice itself is made without importing
anything: whether a shell logger is listening is a question about one
environment variable and one path. Shell integrations can register another
backend through `output_readers.backends.CaptureBackend`; a backend that cannot
answer returns `None`, and the consent-gated replay backend remains last.
"""

from . import backends
from ..utils import without_control_sequences


def _shell_logger_available():
    """Compatibility seam for callers and tests of the old chooser."""
    return backends._shell_logger_available()


def get_output(script, expanded):
    """What the failed command printed, as a rule wants to read it.

    Whichever reader answers, the answer comes back through here, and the
    painting comes off here: colour is something a program does to a terminal
    and every rule below is reading text. See `without_control_sequences` for
    what that was costing.

    """
    return without_control_sequences(_read(script, expanded))


def _read(script, expanded):
    """Get output of the script.

    The first two readers have the output already, recorded as the command ran.
    The third has to run the command a second time to see it, which is only
    allowed when that cannot have an effect or when the user says so — see
    `thebleep.replay`.

    :param script: Console script.
    :type script: str
    :param expanded: Console script with expanded aliases.
    :type expanded: str
    :rtype: str | None

    """
    # Backends are ordered shell logger -> instant log -> replay. A reader that
    # cannot answer returns None, so the next one gets the same command and the
    # replay backend remains the final, consent-gated fallback.
    return backends.read(script, expanded)
