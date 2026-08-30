from thebleep.utils import command_word_index, for_app
# Appends .go when compiling go files
#
# Example:
# > go run foo
# error: go run: no go files listed


@for_app('go')
def match(command):
    start = command_word_index(command.script_parts)
    return (command.script_parts[start:start + 2] == ['go', 'run']
            and not command.script.endswith('.go'))


def get_new_command(command):
    return command.script + '.go'


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
