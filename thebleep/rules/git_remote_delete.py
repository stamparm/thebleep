from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import replace_argument


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    return parts[index:index + 2] == ['remote', 'delete']


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'delete', 'remove')
