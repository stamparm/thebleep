""" Fixes wrong package names with pacman or yaourt.

For example the `llc` program is in package `llvm` so this:
    yay -S llc
should be:
    yay -S llvm
"""

from thebleep.utils import replace_command
from thebleep.specific.archlinux import HELPERS, get_pkgfile, archlinux_env

# pacman itself and every AUR helper that wraps it; `sudo` in front of pacman is
# how it is normally typed. The helpers come from one list, so adding one adds
# it here too.
PACKAGE_MANAGERS = ('pacman',) + HELPERS


def match(command):
    return (command.script_parts
            and (command.script_parts[0] in PACKAGE_MANAGERS
                 or command.script_parts[0:2] == ['sudo', 'pacman'])
            and 'error: target not found:' in command.output)


def get_new_command(command):
    pgr = command.script_parts[-1]

    return replace_command(command, pgr, get_pkgfile(pgr))


enabled_by_default, _ = archlinux_env()
