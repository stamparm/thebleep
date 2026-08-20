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


@git_support
def match(command):
    return ('bisect' in command.script_parts
            and bool(SUBCOMMAND.search(command.script))
            and bool(USAGE.search(command.output)))


@git_support
def get_new_command(command):
    broken = SUBCOMMAND.search(command.script).group(1)
    usage = USAGE.search(command.output).group(1)
    return replace_command(command, broken, usage.split('|'))
