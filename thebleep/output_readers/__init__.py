from .. import replay
from ..conf import settings
from . import read_log, rerun, shell_logger


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
    if shell_logger.is_available():
        return shell_logger.get_output(script)
    if settings.instant_mode:
        return read_log.get_output(script)
    if not replay.is_allowed(script, expanded):
        return None

    return rerun.get_output(script, expanded)
