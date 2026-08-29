from thebleep.utils import replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    return (parts[index:index + 1] == ['add']
            and 'Use -f if you really want to add them.' in command.output)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'add', 'add --force')
