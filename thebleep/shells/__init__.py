"""Package with shell specific actions, each shell class should
implement `from_shell`, `to_shell`, `app_alias`, `put_to_history` and
`get_aliases` methods.

Only the shell actually in use is imported. The classes are still reachable as
attributes of this package, they just arrive when something asks for one.
"""
import os
from importlib import import_module

# Shell name as the alias reports it -> the class that drives it.
shells = {'bash': 'Bash',
          'fish': 'Fish',
          'zsh': 'Zsh',
          'csh': 'Tcsh',
          'tcsh': 'Tcsh',
          'powershell': 'Powershell',
          'pwsh': 'Powershell'}

# Class name -> the module it lives in.
_MODULES = {'Bash': 'bash',
            'Fish': 'fish',
            'Generic': 'generic',
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
    from psutil import Process

    proc = Process(os.getpid())

    while proc is not None and proc.pid > 0:
        try:
            name = proc.name()
        except TypeError:
            name = proc.name

        name = os.path.splitext(name)[0]

        if name in shells:
            return _shell_class(name)()

        try:
            proc = proc.parent()
        except TypeError:
            proc = proc.parent

    return __getattr__('Generic')()


shell = _get_shell_from_env() or _get_shell_from_proc()
