import os
from thebleep.utils import command_word_index, for_app, raw_script_parts, which


@for_app('gradle')
def match(command):
    parts = command.script_parts
    start = command_word_index(parts)
    return (not which(parts[start])
            and 'not found' in command.output
            and os.path.isfile('gradlew'))


def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    parts[start] = './gradlew'
    return ' '.join(parts)
