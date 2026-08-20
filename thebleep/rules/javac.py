"""Appends .java when compiling java files

Example:
 > javac foo
 error: Class names, 'foo', are only accepted if annotation
 processing is explicitly requested

"""
from thebleep.utils import for_app


@for_app('javac')
def match(command):
    return not command.script.endswith('.java')


def get_new_command(command):
    return command.script + '.java'


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
