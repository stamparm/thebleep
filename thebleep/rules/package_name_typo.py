"""`apt install pyhton3` -> `apt install python3`, and dnf's the same way.

    $ apt-get install pyhton3
    E: Unable to locate package pyhton3
    $ dnf install pyhton3
    No match for argument: pyhton3

Neither tool suggests anything, and nothing here did either: a misspelt
package name was the one install mistake with no answer. The names come from
the package manager's own index -- `apt-cache pkgnames`, `dnf repoquery` --
narrowed to the first letter typed, which is a few thousand names to rank
rather than seventy thousand, and read locally: neither goes to the network
for a list it already has. Captured from apt 3.3.3 (debian:testing) and dnf5
5.4.3.0 (fedora:latest).

"""

import re

from thebleep import matching
from thebleep.shells import shell
from thebleep.specific.sudo import sudo_support
from thebleep.utils import command_word_index, for_app, replace_argument, \
    tool_lines

MISSING = (
    # apt and apt-get, `E:` and `Error:` both.
    re.compile(r'Unable to locate package (\S+)'),
    # dnf 4 and 5.
    re.compile(r'No match for argument: (\S+)'),
)


def _broken(output):
    for pattern in MISSING:
        found = pattern.search(output)
        if found:
            return found.group(1)
    return None


def _names(program, broken):
    if program.startswith('apt'):
        arguments = ['apt-cache', 'pkgnames', broken[0]]
    else:
        arguments = [program, 'repoquery', '--available', '-q',
                     '--qf', '%{name}\n', broken[0] + '*']
    return sorted(set(line.strip() for line in tool_lines(arguments)
                      if line.strip()))


@sudo_support
@for_app('apt', 'apt-get', 'dnf', 'dnf5', 'yum')
def match(command):
    return (('Unable to locate package' in command.output
             or 'No match for argument' in command.output)
            and _broken(command.output) in command.script_parts)


@sudo_support
def get_new_command(command):
    broken = _broken(command.output)
    if not broken:
        return []
    program = command.script_parts[command_word_index(command.script_parts)]
    names = [name for name in _names(program, broken) if name != broken]
    # Quoted: a name read out of a package index goes back to the shell.
    return [replace_argument(command.script, broken, shell.quote(name))
            for name in matching.rank(broken, names, limit=3)]
