from thebleep.specific.apt import apt_available
from thebleep.utils import command_word_index, for_app, replace_command_word

enabled_by_default = apt_available


@for_app('apt-get')
def match(command):
    start = command_word_index(command.script_parts)
    return command.script_parts[start:start + 2] == ['apt-get', 'search']


def get_new_command(command):
    return replace_command_word(
        command.script, command_word_index(command.script_parts), 'apt-cache')


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
