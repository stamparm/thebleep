# -*- encoding: utf-8 -*-

"""You committed, and want that commit back -> `git commit --amend`.

This is not a correction of an error. It is for the moment after a commit lands
and you realise you left something out, which is why it keys on the commit
having *worked*.

That was the missing half. `match` was `'commit' in command.script_parts` and
nothing else, so it fired on every `git commit` that failed as well -- and
answered with the literal string `git commit --amend`, whatever had been typed.
Standing in an unresolved merge:

    $ git commit -m "resolve"
    error: Committing is not possible because you have unmerged files.
    $ bleep
    git commit --amend

Amending is not the answer there, `git add` is; and the `-m "resolve"` had gone.
Two changes:

- the previous command has to have **succeeded**, which is what the moment this
  rule is for looks like. A failed commit is somebody else's business.
- `--amend` goes into the command that was typed rather than replacing it, so
  `git commit -m "wip"` becomes `git commit --amend -m "wip"` and the message
  survives.

It needs no output -- the exit status and the command are the whole question --
so it still works when the previous command is not re-read.

"""

from thebleep import replay
from thebleep.utils import replace_argument
from thebleep.specific.git import git_support

requires_output = False


@git_support
def match(command):
    return ('commit' in command.script_parts
            # Exactly zero. `None` means the shell did not say -- an alias from
            # a release before it was reported -- and guessing that a command
            # worked is how this came to answer a failed one.
            and replay.previous_status() == 0)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'commit', 'commit --amend')
