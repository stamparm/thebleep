# -*- encoding: utf-8 -*-

"""`ls` that printed nothing -> `ls -A`, in case the files are hidden ones.

Sound as far as it goes, and it went too far: the only test was that the output
was empty, so a command that had *already* asked for hidden files got the flag
again. `ls -la` in an empty directory was answered with `ls -A -la` -- a
suggestion that changes nothing, offered for a command that had not failed.

"""

from thebleep.utils import (command_word_index, for_app,
                            replace_command_word)

# Every way of saying "show me the hidden ones". `-A` adds nothing to any of
# them.
ALREADY_ASKED = ('--all', '--almost-all')


def _asks_for_hidden(command):
    start = command_word_index(command.script_parts)
    for part in command.script_parts[start + 1:]:
        if part in ALREADY_ASKED:
            return True
        # A short-flag bundle: `-la`, `-Al`, `-a`.
        if part.startswith('-') and not part.startswith('--'):
            if 'a' in part or 'A' in part:
                return True

    return False


@for_app('ls')
def match(command):
    return command.output.strip() == '' and not _asks_for_hidden(command)


def get_new_command(command):
    # Keep the user's original quoting: `ls 'a;touch marker'` is one literal
    # path, and rebuilding it from `script_parts` would turn the semicolon
    # into shell syntax in the suggestion.
    start = command_word_index(command.script_parts)
    return replace_command_word(command.script, start, 'ls -A')
