""" This file provide some utility functions for Arch Linux specific rules."""
from .. import utils


@utils.memoize
def get_pkgfile(command):
    """ Gets the packages that provide the given command using `pkgfile`.

    If the command is of the form `sudo foo`, searches for the `foo` command
    instead.
    """
    command = command.strip()

    if command.startswith('sudo '):
        command = command[5:]

    command = command.split(" ")[0]

    # Through `tool_lines`, which is where the timeout is: `pkgfile` reads a
    # package database that may be on a network mount, and this runs from a
    # rule's `match`. It also swallows what the three `except` clauses here used
    # to catch -- pkgfile not installed, pkgfile finding nothing and exiting 1,
    # pkgfile gone since the rule was enabled -- and answers `[]` to all of
    # them, which is what each of them meant.
    packages = utils.tool_lines(['pkgfile', '-b', '-v', command])

    return [package.split()[0] for package in packages if package.split()]


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
