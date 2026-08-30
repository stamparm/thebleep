from thebleep.specific.npm import npm_available, get_scripts
from thebleep.utils import command_word_index, for_app, raw_script_parts

enabled_by_default = npm_available


@for_app('npm')
def match(command):
    # A bare `npm` prints this usage too, and there is no second word to look
    # up -- `script_parts[1]` was an `IndexError`.
    parts = command.script_parts
    start = command_word_index(parts)
    return (len(parts) > start + 1
            and 'Usage: npm <command>' in command.output
            and not any(part.startswith('ru') for part in parts[start + 1:])
            and parts[start + 1] in get_scripts())


def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    parts.insert(start + 1, 'run-script')
    return ' '.join(parts)
