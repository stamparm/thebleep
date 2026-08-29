from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import replace_argument


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['rm']
            and "fatal: not removing '" in command.output
            and "' recursively without -r" in command.output)


@git_support
def get_new_command(command):
    return replace_argument(command.script, 'rm', 'rm -r')
