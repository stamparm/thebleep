"""Where the output of the command that failed comes from.

Three readers. A correction normally uses one of them -- and in instant mode,
where the recording turns out to hold no answer, falls through from that one to
the replay path with its question intact. They used to all be
imported here, so every correction paid for all three: `shell_logger` brings in
`socket` and `json`, `rerun` brings in `subprocess` and the threading and
signal machinery underneath it, and `read_log` brings in `mmap` and `re`. On
Windows, where finding and opening a module is the dearest thing an interpreter
does, that was three readers' worth of imports to use one.

So each arrives when it is chosen. The choice itself is made without importing
anything: whether a shell logger is listening is a question about one
environment variable and one path.
"""

import os
from .. import const
from ..conf import settings


def _shell_logger_available():
    """Whether a shell logger is listening, asked without importing one.

    `shell_logger.is_available()` is still what answers, and still the thing to
    patch -- but it is only asked once the environment says a logger might be
    there. Without that variable the answer is `False` and the module never
    needs to be found, opened or executed.

    """
    if not os.environ.get(const.SHELL_LOGGER_SOCKET_ENV):
        return False

    from . import shell_logger
    return shell_logger.is_available()


def get_output(script, expanded):
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
    if _shell_logger_available():
        from . import shell_logger

        output = shell_logger.get_output(script)
        if output is not None:
            return output
        # The logger is an optimisation, and one that answers over a socket to
        # a separate process: a daemon that died and left its socket file
        # behind, one that accepts and then says nothing, a reply that is not
        # the JSON expected. Returning its answer directly made every one of
        # those the end of the correction. It is now a reader like the others,
        # and a reader with no answer is fallen through.
    if settings.instant_mode:
        from . import read_log

        output = read_log.get_output(script)
        if output is not None:
            return output
        # The recording could not answer -- no mark in `PS1`, no recording, or
        # the command is not in the window any more, each of which `read_log`
        # has already said out loud. Instant mode is then simply not in play for
        # this correction, so it takes the ordinary route, which is to ask
        # before running anything a second time. Falling through rather than
        # giving up is what makes "where it does not work, it does not go
        # wrong" true; `replay.is_allowed` below is untouched, so nothing gained
        # consent by this path that would not have had it anyway.

    from .. import replay
    if not replay.is_allowed(script, expanded):
        return None

    from . import rerun
    return rerun.get_output(script, expanded)
