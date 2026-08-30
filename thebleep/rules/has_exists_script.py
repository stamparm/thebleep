import os
from thebleep.specific.sudo import sudo_support
from thebleep.utils import command_word_index, raw_script_parts


@sudo_support
def match(command):
    return (command.script_parts
            and command_word_index(command.script_parts)
            < len(command.script_parts)
            and os.path.exists(command.script_parts[command_word_index(
                command.script_parts)])
            and 'command not found' in command.output)


@sudo_support
def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    target = parts[start]
    return command.script.replace(target, './' + target, 1)
