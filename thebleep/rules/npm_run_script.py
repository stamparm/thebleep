from thebleep.specific.npm import npm_available, get_scripts
from thebleep.utils import for_app

enabled_by_default = npm_available


@for_app('npm')
def match(command):
    # A bare `npm` prints this usage too, and there is no second word to look
    # up -- `script_parts[1]` was an `IndexError`.
    return (len(command.script_parts) > 1
            and 'Usage: npm <command>' in command.output
            and not any(part.startswith('ru') for part in command.script_parts)
            and command.script_parts[1] in get_scripts())


def get_new_command(command):
    parts = command.script_parts[:]
    parts.insert(1, 'run-script')
    return ' '.join(parts)
