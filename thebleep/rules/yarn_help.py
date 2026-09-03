import re
from thebleep.utils import command_word_index, for_app
from thebleep.system import open_command


@for_app('yarn', at_least=2)
def match(command):
    parts = command.script_parts
    start = command_word_index(parts)
    return (parts[start + 1] == 'help'
            and 'for documentation about this command.' in command.output)


def get_new_command(command):
    found = re.findall(
        r'Visit ([^ ]*) for documentation about this command.',
        command.output)
    return open_command(found[0]) if found else []
