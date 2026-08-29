from thebleep.utils import replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    return (parts[index:index + 1] == ['tag']
            and 'already exists' in command.output)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'tag', 'tag --force')
