# -*- encoding: utf-8 -*-

"""`ls` that printed nothing -> `ls -A`, in case the files are hidden ones.

Sound as far as it goes, and it went too far: the only test was that the output
was empty, so a command that had *already* asked for hidden files got the flag
again. `ls -la` in an empty directory was answered with `ls -A -la` -- a
suggestion that changes nothing, offered for a command that had not failed.

"""

import re

from thebleep.utils import for_app

# Every way of saying "show me the hidden ones". `-A` adds nothing to any of
# them.
ALREADY_ASKED = ('--all', '--almost-all')


def _asks_for_hidden(command):
    for part in command.script_parts[1:]:
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
    return re.sub(r'^ls(?=\s|$)', 'ls -A', command.script, count=1)
