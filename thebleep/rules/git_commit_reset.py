# -*- encoding: utf-8 -*-

"""You committed, and want the commit undone -> `git reset HEAD~`.

Like its sibling `git_commit_amend`, this is not a correction of an error. It is
for the moment after a commit lands and you wish it had not, which is why it
keys on the commit having *worked*.

That was the missing half, and missing it here cost more than it does anywhere
else in this repository, because `git reset HEAD~` throws a commit away. `match`
was `'commit' in command.script_parts` and nothing else, so it fired on every
`git commit` that *failed* -- and every failed commit is a commit that has not
happened, so the thing it offered to undo was the one before it:

    $ git commit -m "the fix"
    pre-commit hook failed: 3 lint errors
    $ bleep
    git reset HEAD~           <- drops the commit before this one

A failed hook, unmerged files, a stale index lock: none of them is this rule's
business, and each of them left the previous commit one keystroke from gone.

So the previous command has to have succeeded. It needs no output -- the exit
status and the command are the whole question -- so it still works when the
previous command is not re-read.

"""

from thebleep import replay
from thebleep.specific.git import git_subcommand_index, git_support

requires_output = False


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    return (parts[index:index + 1] == ['commit']
            # Exactly zero. `None` means the shell did not say, and guessing
            # that a commit worked is how this came to answer a failed one by
            # discarding the commit before it.
            and replay.previous_status() == 0)


@git_support
def get_new_command(command):
    return 'git reset HEAD~'
