from thebleep.specific.git import git_support
from thebleep.utils import command_word_index, replace_argument


@git_support
def match(command):
    parts = command.script_parts
    index = command_word_index(parts)
    return parts[index + 1:index + 3] == ['remote', 'delete']


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'delete', 'remove')
