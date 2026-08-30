import os
from thebleep.utils import command_word_index, for_app, replace_command_word


def _is_recursive(part):
    if part == '--recurse':
        return True
    elif not part.startswith('--') and part.startswith('-') and 'r' in part:
        return True


def _isdir(part):
    return not part.startswith('-') and os.path.isdir(part)


@for_app('prove')
def match(command):
    start = command_word_index(command.script_parts)
    return (
        'NOTESTS' in command.output
        and not any(_is_recursive(part)
                    for part in command.script_parts[start + 1:])
        and any(_isdir(part) for part in command.script_parts[start + 1:]))


def get_new_command(command):
    return replace_command_word(
        command.script, command_word_index(command.script_parts), 'prove -r')
