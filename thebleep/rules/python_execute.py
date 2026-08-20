# Appends .py when executing python files
#
# Example:
# > python foo
# error: python: can't open file 'foo': [Errno 2] No such file or directory
from thebleep.utils import for_app


@for_app('python')
def match(command):
    return not command.script.endswith('.py')


def get_new_command(command):
    return command.script + '.py'


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
