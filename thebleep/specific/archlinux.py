""" This file provide some utility functions for Arch Linux specific rules."""
import subprocess
from .. import utils


@utils.memoize
def get_pkgfile(command):
    """ Gets the packages that provide the given command using `pkgfile`.

    If the command is of the form `sudo foo`, searches for the `foo` command
    instead.
    """
    try:
        command = command.strip()

        if command.startswith('sudo '):
            command = command[5:]

        command = command.split(" ")[0]

        packages = subprocess.check_output(
            ['pkgfile', '-b', '-v', command],
            universal_newlines=True, stderr=utils.DEVNULL
        ).splitlines()

        return [package.split()[0] for package in packages]
    except subprocess.CalledProcessError as err:
        if err.returncode == 1 and err.output == "":
            return []
        else:
            raise err
    except OSError:
        # pkgfile is not installed, or went away since the rule was enabled.
        return []


# The AUR helpers, in the order they are looked for. `paru` first because it is
# what most of Arch moved to when `yay` slowed down, and `yaourt` last because
# it has been unmaintained since 2018 and is only still here for the machines
# that still have it.
#
# Refs: nvbn/thefuck#1514
HELPERS = ('paru', 'yay', 'pikaur', 'yaourt')


def archlinux_env():
    for helper in HELPERS:
        if utils.which(helper):
            pacman = helper
            break
    else:
        if utils.which('pacman'):
            pacman = 'sudo pacman'
        else:
            return False, None

    enabled_by_default = utils.which('pkgfile')

    return enabled_by_default, pacman
