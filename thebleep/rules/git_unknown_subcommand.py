# -*- encoding: utf-8 -*-

"""`git remote ad origin x` -> `git remote add origin x`.

git has a dozen commands that dispatch again on a second word -- `remote`,
`submodule`, `worktree`, `notes`, `sparse-checkout`, `bisect` -- and a typo in
that second word got nothing at all, from any rule. `git_not_command` reads
git's "most similar command" suggestion, and git makes no such suggestion here;
it prints its usage instead:

    $ git remote ad origin x
    error: unknown subcommand: `ad'
    usage: git remote [-v | --verbose]
       or: git remote add [-t <branch>] ... <name> <url>
       or: git remote rename [--[no-]progress] <old> <new>
       ...

Which is a list of the answers, in the message, going unread. So this reads it.
Because the list is git's own, the candidates are *ordered* rather than filtered
-- see `matching.order` for why that distinction matters.

Four shapes of usage line, all of them real:

    usage: git remote [-v | --verbose]                     the command alone
       or: git remote add [-t <branch>] ...                 command, subcommand
       or: git submodule [--quiet] add [-b <branch>] ...    an option between
    usage: git sparse-checkout (init | list | set | ...)    an alternation

Captured from git 2.43.

"""

import re
from thebleep import matching
from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import memoize, replace_argument_in_command

# ``error: unknown subcommand: `ad' `` -- git's own quoting, a backtick and a
# quote.
UNKNOWN = re.compile(r"unknown subcommand: [`']([^'`]+)'")

# A usage line, however it is introduced.
USAGE = re.compile(r'^\s*(?:usage:|or:)\s+(.*)$', re.MULTILINE)

# A subcommand as git spells one: lower case, letters and hyphens.
NAME = re.compile(r'^[a-z][a-z-]*$')


def _subcommands(output, command):
    """The second words git listed for `command`, in the order it listed them.

    An alternation -- `(init | list | set)` -- is expanded, and an option
    between the command and its subcommand is stepped over, which is how
    `git submodule [--quiet] add ...` reads.

    """
    found = []
    for line in USAGE.findall(output):
        words = line.replace('(', ' ').replace(')', ' ') \
                    .replace('|', ' ').split()
        if not words or words[0] != 'git':
            continue

        rest = words[1:]
        if not rest or rest[0] != command:
            continue

        for word in rest[1:]:
            if word.startswith(('[', '-', '<')):
                # An option or a placeholder: keep looking along the line.
                continue
            if NAME.match(word) and word not in found:
                found.append(word)
            # The alternation puts several on one line, so this does not stop
            # at the first -- but anything after a placeholder is an argument,
            # not a subcommand.
            if word.startswith('<'):
                break

    return found


@memoize
def _typo_and_answers(command):
    """`(what git could not read, what it could)`, or `None`."""
    named = UNKNOWN.search(command.output)
    if not named:
        return None

    parts = command.script_parts
    index = git_subcommand_index(parts)
    if index + 1 >= len(parts):
        return None

    # The command that dispatched, which is the first word after `git` that is
    # not an option.
    dispatcher = parts[index]

    answers = _subcommands(command.output, dispatcher)
    typo = named.group(1)
    answers = [name for name in answers if name != typo]
    if not answers:
        return None

    return typo, answers


@git_support
def match(command):
    return _typo_and_answers(command) is not None


@git_support
def get_new_command(command):
    typo, answers = _typo_and_answers(command)

    # Quoted: read out of git's output, and handed back to the shell.
    return [
        replace_argument_in_command(command, 'git', typo, shell.quote(name))
        for name in matching.order(typo, answers, limit=3)]
