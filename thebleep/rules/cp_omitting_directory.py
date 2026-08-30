from thebleep.specific.sudo import sudo_support
from thebleep.utils import command_word_index, for_app, replace_command_word


@sudo_support
@for_app('cp')
def match(command):
    output = command.output.lower()
    return 'omitting directory' in output or 'is a directory' in output


@sudo_support
def get_new_command(command):
    return replace_command_word(
        command.script, command_word_index(command.script_parts), 'cp -a')
