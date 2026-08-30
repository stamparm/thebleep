from thebleep.utils import (command_word_index, get_all_executables,
                            raw_script_parts)
from thebleep.specific.sudo import sudo_support


@sudo_support
def match(command):
    start = command_word_index(command.script_parts)
    if start == len(command.script_parts):
        return False
    first_part = command.script_parts[start]
    if "-" not in first_part or first_part in get_all_executables():
        return False
    cmd, _ = first_part.split("-", 1)
    return cmd in get_all_executables()


@sudo_support
def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    target = parts[start]
    return command.script.replace(target, target.replace('-', ' ', 1), 1)


priority = 4500
requires_output = False
