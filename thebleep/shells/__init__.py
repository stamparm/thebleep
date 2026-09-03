"""Package with shell specific actions, each shell class should
implement `from_shell`, `to_shell`, `app_alias`, `put_to_history` and
`get_aliases` methods.

Only the shell actually in use is imported. The classes are still reachable as
attributes of this package, they just arrive when something asks for one.
"""
import os
from importlib import import_module
from ..const import SHELLS as shells  # noqa: F401  (re-exported by name)

# Class name -> the module it lives in.
_MODULES = {'Bash': 'bash',
            'Fish': 'fish',
            'Generic': 'generic',
            'Ksh': 'ksh',
            'Nushell': 'nushell',
            'Tcsh': 'tcsh',
            'Zsh': 'zsh',
            'Powershell': 'powershell'}


def __getattr__(name):
    """Imports a shell class the first time it is asked for."""
    module_name = _MODULES.get(name)
    if module_name is None:
        raise AttributeError(
            '{!r} has no attribute {!r}'.format(__name__, name))
    value = getattr(import_module('.' + module_name, __name__), name)
    globals()[name] = value
    return value


def _shell_class(name):
    return __getattr__(shells[name])


def _get_shell_from_env():
    name = os.environ.get('TB_SHELL')

    if name in shells:
        return _shell_class(name)()


def _get_shell_from_proc():
    # Only reached when the alias didn't tell us the shell, so psutil is
    # imported here rather than at startup.
    import psutil

    # Walking up the tree can fail at any step: a parent may exit while we are
    # looking at it, and after leaving a `sudo su` session the processes above
    # us belong to root and are no longer ours to read. Neither is a reason to
    # give up on the whole run, so the walk stops and the generic shell
    # answers instead.
    unreadable = (psutil.AccessDenied, psutil.NoSuchProcess,
                  psutil.ZombieProcess, psutil.TimeoutExpired, OSError)

    try:
        proc = psutil.Process(os.getpid())
    except unreadable:
        proc = None

    while proc is not None and proc.pid > 0:
        try:
            name = proc.name()
        except TypeError:
            name = proc.name
        except unreadable:
            break

        name = os.path.splitext(name)[0]

        if name in shells:
            return _shell_class(name)()

        try:
            proc = proc.parent()
        except TypeError:
            proc = proc.parent
        except unreadable:
            break

    return __getattr__('Generic')()


shell = _get_shell_from_env() or _get_shell_from_proc()
