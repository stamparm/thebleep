# -*- encoding: utf-8 -*-

import re

# Appends -lah when ls ran but showed nothing hidden
#
# Example:
# > ls
# file.txt
from thebleep.utils import for_app

# The ways an `ls` says it failed rather than listed. A rule that answers any
# output at all was answering these too:
#
#     $ ls /nonexistent-dir-xyz
#     ls -lah /nonexistent-dir-xyz
#
# -- more flags offered to a command that had just said the argument was not
# there. Hidden files were never the question, and rerunning it fails again.
_FAILURES = ('cannot access',
             'No such file or directory',
             'Not a directory')


@for_app('ls')
def match(command):
    if not command.script_parts or 'ls -' in command.script:
        return False

    return not any(failure in command.output
                   for failure in _FAILURES)


def get_new_command(command):
    return re.sub(r'^ls(?=\s|$)', 'ls -lah', command.script, count=1)


# The error check above is the whole point now; without the output there is
# nothing to tell a listing from a failure.
requires_output = True
