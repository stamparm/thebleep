# -*- encoding: utf-8 -*-

"""`git stash pp` -> `git stash pop`, and `git stash a message` -> `save`.

Dead against any current git. The rule looked for `usage:` in the output, and
git stopped printing a usage block for this years ago:

    $ git stash pp
    fatal: subcommand wasn't specified; 'push' can't be assumed due to
    unexpected token 'pp'

No `usage:`, so no match, so `git stash pp` went uncorrected -- and the message
that replaced it is *better* than the usage block, because it names the token
git could not make sense of. The rule used to take the third word of the command
on the assumption that that was it, which is wrong the moment there is an option
in front of it (`git stash -q saev`).

Both wordings are matched: the modern one, and the usage block for the git
versions that still print it.

Wordings captured from git 2.43.

"""

import re
from thebleep import utils
from thebleep.utils import replace_argument
from thebleep.specific.git import git_support

# git 2.x: the token it could not read, named.
UNEXPECTED = re.compile(r"unexpected token '([^']+)'")


def _bad_token(command):
    """The word git could not make sense of, or `None`."""
    named = UNEXPECTED.search(command.output)
    if named:
        return named.group(1)

    if 'usage:' not in command.output:
        return None

    # The old usage block names nothing, so the first word after `stash` that
    # is not an option is the guess -- which is what this always did, only
    # without assuming that word is at index 2.
    for part in command.script_parts[2:]:
        if not part.startswith('-'):
            return part

    return None


# git's own list, which is stable and short. Asking git for it means running
# `git stash --help`, and a manual page is not a list.
stash_commands = (
    'apply',
    'branch',
    'clear',
    'drop',
    'list',
    'pop',
    'push',
    'save',
    'show')


@git_support
def match(command):
    return (len(command.script_parts) > 2
            and command.script_parts[1] == 'stash'
            and _bad_token(command) is not None)


@git_support
def get_new_command(command):
    stash_cmd = _bad_token(command)
    if stash_cmd is None:
        return []

    fixed = utils.get_closest(stash_cmd, stash_commands,
                              fallback_to_first=False)

    if fixed is not None:
        return replace_argument(command.script, stash_cmd, fixed)

    # Not a misspelt subcommand, so it was meant as a message -- which is what
    # `git stash save` takes.
    cmd = command.script_parts[:]
    cmd.insert(2, 'save')
    return ' '.join(cmd)
