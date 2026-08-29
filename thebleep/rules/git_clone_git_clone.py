from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import remove_argument_sequence


@git_support
def match(command):
    parts = command.script_parts
    index = git_subcommand_index(command.script_parts)
    return (index < len(command.script_parts)
            and parts[index] == 'clone'
            and any(parts[pos:pos + 2] == ['git', 'clone']
                    for pos in range(index + 1, len(parts) - 1))
            and 'fatal: Too many arguments.' in command.output)


@git_support
def get_new_command(command):
    index = git_subcommand_index(command.script_parts)
    return remove_argument_sequence(command.script, ('git', 'clone'),
                                    start=index + 1)
