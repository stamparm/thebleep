from types import ModuleType
from thebleep.specific.apt import apt_available
from thebleep.utils import memoize, which
from thebleep.shells import shell

try:
    from CommandNotFound import CommandNotFound

    enabled_by_default = apt_available

    if isinstance(CommandNotFound, ModuleType):
        # For ubuntu 18.04+
        _get_packages = CommandNotFound.CommandNotFound().get_packages
    else:
        # For older versions
        _get_packages = CommandNotFound().getPackages
except ImportError:
    enabled_by_default = False
    # Named so that `get_package` below raises nothing worse than "no package
    # found" when somebody enables this rule on a machine that has no
    # python3-commandnotfound. It used to be a NameError on every correction.
    _get_packages = None


def _get_executable(command):
    parts = command.script_parts
    if parts and parts[0] == 'sudo':
        # `sudo` on its own is a thing people type, and then there is no
        # executable to go looking for a package for.
        return parts[1] if len(parts) > 1 else None
    return parts[0] if parts else None


@memoize
def get_package(executable):
    if _get_packages is None:
        return None

    try:
        packages = _get_packages(executable)
        return packages[0][0]
    except IndexError:
        # IndexError is thrown when no matching package is found
        return None


def match(command):
    if 'not found' in command.output or 'not installed' in command.output:
        executable = _get_executable(command)
        return bool(executable) and not which(executable) \
            and bool(get_package(executable))
    else:
        return False


def get_new_command(command):
    executable = _get_executable(command)
    name = get_package(executable)
    return shell.and_(u'sudo apt-get install {}'.format(shell.quote(name)),
                      command.script)
