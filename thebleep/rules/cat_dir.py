import os
from thebleep.utils import command_word_index, for_app, raw_script_parts


@for_app('cat', at_least=1)
def match(command):
    parts = command.script_parts
    start = command_word_index(parts)
    return (
        'cat: ' in command.output and
        command.output.startswith('cat: ') and
        os.path.isdir(parts[start + 1])
    )


def get_new_command(command):
    raw_parts = raw_script_parts(command.script)
    start = command_word_index(raw_parts)
    executable = command.script_parts[start]
    directory = os.path.dirname(executable)
    raw_parts[start] = os.path.join(directory, 'ls') if directory else 'ls'
    return ' '.join(raw_parts)
