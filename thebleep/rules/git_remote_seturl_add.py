from thebleep.utils import replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 2] == ['remote', 'set-url']
            # `fatal:` up to git 2.4x, `error: No such remote 'x'` in 2.53.
            and 'No such remote' in command.output)


def get_new_command(command):
    return replace_argument(command.script, 'set-url', 'add')
