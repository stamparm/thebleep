# -*- encoding: utf-8 -*-

"""`git bisect strt` -> `git bisect start`, from the usage git prints.

    $ git bisect strt
    usage: git bisect [help|start|bad|good|new|old|terms|skip|next|reset|...]

The subcommand is read out of that list, so the rule needs both a subcommand to
correct and a list to correct it against. Neither was checked:

- `git bisect` on its own -- which is how you find out you forgot the
  subcommand -- has nothing after `bisect`, and the regex returned no match. The
  `[0]` on it raised `IndexError` and printed a traceback.
- git 2.47 answers a bare `git bisect` with `fatal: need a command` and no usage
  line at all, so there is nothing to offer and this correctly does not match.

Captured from git 2.30.2 and 2.39.5 (usage line) and 2.47.3 (`need a command`).

"""

import re
from thebleep.utils import replace_command
from thebleep.specific.git import git_support

SUBCOMMAND = re.compile(r'git bisect\s+(\S+)')
USAGE = re.compile(r'usage: git bisect \[([^\]]+)\]')
# git 2.53 and later: `fatal: unknown command: 'strt'`, then one line per
# subcommand -- `usage: git bisect start ...`, `   or: git bisect next`,
# `   or: git bisect (good|old|<term-old>) ...`.
USAGE_LINE = re.compile(r'^\s*(?:usage|or): git bisect (\([^)]*\)|[\w-]+)',
                        re.MULTILINE)


def _subcommands(output):
    listed = USAGE.search(output)
    if listed:
        return listed.group(1).split('|')
    names = []
    for found in USAGE_LINE.findall(output):
        for name in found.strip('()').split('|'):
            if name and not name.startswith('<') and name not in names:
                names.append(name)
    return names


@git_support
def match(command):
    return ('bisect' in command.script_parts
            and bool(SUBCOMMAND.search(command.script))
            and 'git bisect' in command.output
            and bool(_subcommands(command.output)))


@git_support
def get_new_command(command):
    broken = SUBCOMMAND.search(command.script).group(1)
    return replace_command(command, broken, _subcommands(command.output),
                           guessed=True)
