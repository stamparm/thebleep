import re
from thebleep.shells import shell
from thebleep.utils import replace_argument
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['merge']
            and ' - not something we can merge' in command.output
            and 'Did you mean this?' in command.output)


@git_support
def get_new_command(command):
    unknown_branch = re.findall(r'merge: (.+) - not something we can merge', command.output)[0]
    remote_branch = re.findall(r'Did you mean this\?\n\t([^\n]+)', command.output)[0]

    # `remote_branch` is a branch name from the remote, and a branch name is
    # allowed to be shell syntax.
    return replace_argument(command.script, unknown_branch,
                            shell.quote(remote_branch))
