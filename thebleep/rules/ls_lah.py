from thebleep.utils import for_app


@for_app('ls')
def match(command):
    return command.script_parts and 'ls -' not in command.script


def get_new_command(command):
    command = command.script_parts[:]
    command[0] = 'ls -lah'
    return ' '.join(command)


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
