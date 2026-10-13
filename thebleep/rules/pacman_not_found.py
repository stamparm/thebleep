""" Fixes wrong package names with pacman or yaourt.

For example the `llc` program is in package `llvm` so this:
    yay -S llc
should be:
    yay -S llvm
"""

from thebleep.utils import command_word_index, replace_command
from thebleep.specific.archlinux import HELPERS, get_pkgfile, archlinux_env

# pacman itself and every AUR helper that wraps it; `sudo` in front of pacman is
# how it is normally typed. The helpers come from one list, so adding one adds
# it here too.
PACKAGE_MANAGERS = ('pacman',) + HELPERS


def match(command):
    start = command_word_index(command.script_parts)
    return (start < len(command.script_parts)
            and (command.script_parts[start] in PACKAGE_MANAGERS
                 or command.script_parts[start:start + 2] == ['sudo', 'pacman'])
            and 'error: target not found:' in command.output)


import re  # noqa: E402

TARGET = re.compile(r'error: target not found: (\S+)')


def get_new_command(command):
    # The package pacman named, not the last word: `pacman -S llc --needed`
    # ends in an option.
    found = TARGET.search(command.output)
    if not found:
        return []
    pgr = found.group(1)
    providers = get_pkgfile(pgr)
    if providers:
        return replace_command(command, pgr, providers)
    # No package provides a program by that name, so it is a package name
    # misspelt -- `pacman -S pyhton` (pacman 7.1.0, archlinux) -- and the sync
    # databases already list every name there is.
    from thebleep import matching
    from thebleep.utils import tool_lines

    names = [name for name in tool_lines(['pacman', '-Slq']) if name != pgr]
    return replace_command(command, pgr, matching.rank(pgr, names, limit=3))


enabled_by_default, _ = archlinux_env()
