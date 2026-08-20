# -*- encoding: utf-8 -*-

"""`git diff` that showed nothing -> `git diff --staged`.

The everyday confusion: you staged your changes, `git diff` prints nothing
because there is nothing left unstaged, and what you wanted was `--staged`.

Which means it is a rule about a `git diff` that *worked*. `match` was
`'diff' in command.script and '--staged' not in command.script`, so it fired on
every failing `git diff` as well, and added `--staged` while leaving the real
error in place:

    $ git diff README.md --cached
    fatal: option '--cached' must come before non-option arguments
    $ bleep
    git diff --staged README.md --cached

The offending `--cached` is still there, so the suggestion fails in exactly the
same way -- and `git_flag_after_filename`, which knows that message and gets it
right, was behind it in the ordering. So this now wants the previous command to
have succeeded, and stands aside otherwise.

It needs no output: the exit status and the command are the whole question.

"""

from thebleep import replay
from thebleep.utils import replace_argument
from thebleep.specific.git import git_support

requires_output = False


@git_support
def match(command):
    return ('diff' in command.script_parts
            and '--staged' not in command.script
            and '--cached' not in command.script
            # Exactly zero: `None` means the shell did not say, and guessing
            # that a command worked is what put `--staged` in front of an error
            # message.
            and replay.previous_status() == 0)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'diff', 'diff --staged')
