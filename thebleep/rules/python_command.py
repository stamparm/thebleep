from thebleep.specific.sudo import sudo_support
from thebleep.utils import command_word_index, raw_script_parts
# add 'python' suffix to the command if
#  1) The script does not have execute permission or
#  2) is interpreted as shell script


@sudo_support
def match(command):
    return (command.script_parts
            and command_word_index(command.script_parts)
            < len(command.script_parts)
            and command.script_parts[command_word_index(
                command.script_parts)].endswith('.py')
            and ('Permission denied' in command.output or
                 'command not found' in command.output))


@sudo_support
def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    target = parts[start]
    return command.script.replace(target, 'python ' + target, 1)
