from thebleep.utils import command_word_index, replace_argument
from thebleep.specific.git import git_support


@git_support
def match(command):
    parts = command.script_parts
    index = command_word_index(parts)
    return (parts[index + 1:index + 2] == ['add']
            and 'Use -f if you really want to add them.' in command.output)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'add', 'add --force')
