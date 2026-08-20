"""Fixes common java command mistake

Example:
> java foo.java
Error: Could not find or load main class foo.java

"""
from thebleep.utils import for_app


@for_app('java')
def match(command):
    return command.script.endswith('.java')


def get_new_command(command):
    return command.script[:-5]


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
