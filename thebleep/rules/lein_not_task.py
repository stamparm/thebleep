import re
from thebleep.utils import replace_command, get_all_matched_commands, for_app
from thebleep.specific.sudo import sudo_support


@sudo_support
@for_app('lein')
def match(command):
    return ("is not a task. See 'lein help'" in command.output
            and 'Did you mean this?' in command.output)


@sudo_support
def get_new_command(command):
    found = re.findall(r"'([^']*)' is not a task", command.output)
    if not found:
        return []
    new_cmds = get_all_matched_commands(command.output, 'Did you mean this?')
    return replace_command(command, found[0], new_cmds)
