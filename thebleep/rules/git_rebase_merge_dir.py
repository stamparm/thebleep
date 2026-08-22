# -*- encoding: utf-8 -*-

"""A rebase blocked by a leftover `rebase-merge` directory.

git tells you the four ways out, and this offers them. The one worth having is
the last -- `rm -fr ".git/rebase-merge"` -- and it was the one that never
arrived, because it was found by counting backwards from the end of the output:

    $ git rebase master
    fatal: It seems that there is already a rebase-merge directory, and
    I wonder if you are in the middle of another rebase.  If that is the
    case, please try
            git rebase (--continue | --abort | --skip)
    If that is not the case, please
            rm -fr ".git/rebase-merge"
    and run me again.  I am stopping in case you still have something
    valuable there.

    $ bleep
    and run me again.  I am stopping in case you still have something

The real message ends with a blank line, so `split('\\n')[-4]` lands on a
sentence of prose two lines above the `rm`. Offered as a command, it is not one;
and the `rm` -- the whole reason the rule reads the output at all rather than
listing the three `--` options it already knows -- was never offered.

So the line is found by looking for it. Which also survives a reader that
strips the output, and this project has two of those.

Wording captured from git 2.43.

"""

import re
from thebleep.shells import shell
from thebleep.utils import get_close_matches
from thebleep.specific.git import git_support

# The line git offers, indented by a tab, naming the directory in quotes. The
# directory is read out of the message rather than assumed to be
# `.git/rebase-merge`, because `--git-dir`, a worktree and `GIT_DIR` all move
# it, and git has already worked out where it is.
REMOVE = re.compile(r'^\s*rm -fr "([^"]+)"\s*$', re.MULTILINE)


@git_support
def match(command):
    return (' rebase' in command.script and
            'It seems that there is already a rebase-merge directory' in command.output and
            'I wonder if you are in the middle of another rebase' in command.output)


@git_support
def get_new_command(command):
    command_list = ['git rebase --continue', 'git rebase --abort', 'git rebase --skip']

    found = REMOVE.search(command.output)
    if found:
        # Quoted here, though not in git's message: the path came out of the
        # output and this goes to a shell, and the double quotes git prints do
        # not stop a `$(...)` or a backtick that a directory name contains.
        # `shell.quote` does; for the ordinary path it adds nothing at all.
        command_list.append(
            'rm -fr {}'.format(shell.quote(found.group(1))))

    return get_close_matches(command.script, command_list, 4, 0)
