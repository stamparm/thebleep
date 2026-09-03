"""`vim: command not found` -> `sudo apt-get install vim && vim`. But not
always the right guess when the name is short:

    $ gt diff
    Command 'gt' not found, but can be installed with:
    sudo apt install genometools
    $ bleep
    sudo apt-get install genometools && gt diff   <- and `git diff` was one
                                                       edit away, already
                                                       installed

apt's own suggestion is an exact match on the name you typed, which sounds
like certainty but is not: `gt` is not a typo apt can see, it is the actual
name of a real, unrelated package, and on a machine with tens of thousands of
them a short name colliding with one is unremarkable. `no_command`'s "git" is
weaker-looking evidence -- an edit away, not exact -- but it is a program
already on this machine, so acting on it costs nothing to try and nothing to
undo. Offering to install a stranger's package before that is asked is
backwards, so this answers after `no_command`, at 3100, rather than before it
at the default 1000.

"""

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


# After `no_command`, at 3100: a typo of something already installed beats
# installing a look-alike package, and only outranks the guess-tier rules
# below `no_command` because those have nothing to say about a name apt
# recognises.
priority = 3100
