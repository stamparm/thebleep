import re
from thebleep.utils import command_word_index, for_app, replace_argument


warning_regex = re.compile(r'Warning: (?:.(?!is ))+ is already installed and '
                           r'up-to-date')
# brew puts the command on the line below now -- `To reinstall 5.8.3, run:`
# and then `  brew reinstall xz` -- where it used to be inline in backticks.
message_regex = re.compile(r'To reinstall (?:(?!, ).)+, run:?\s*`?'
                           r'brew reinstall ')


@for_app('brew', at_least=2)
def match(command):
    parts = command.script_parts
    start = command_word_index(parts)
    return (parts[start + 1] == 'install'
            and warning_regex.search(command.output)
            and message_regex.search(command.output))


def get_new_command(command):
    return replace_argument(command.script, 'install', 'reinstall')
