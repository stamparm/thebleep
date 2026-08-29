from thebleep.utils import replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['pull']
            and 'fatal: not a git repository' in command.output.lower()
            and "Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set)." in command.output)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'pull', 'clone')
