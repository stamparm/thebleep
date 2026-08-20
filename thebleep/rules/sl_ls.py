"""
This happens way too often

When typing really fast cause I'm a 1337 H4X0R,
I often mistype 'ls' as 'sl'. No more!
"""


def match(command):
    return command.script == 'sl'


def get_new_command(command):
    return 'ls'


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
