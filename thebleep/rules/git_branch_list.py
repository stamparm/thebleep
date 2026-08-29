from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    # catches "git branch list" in place of "git branch"
    index = git_subcommand_index(command.script_parts)
    return (index < len(command.script_parts)
            and command.script_parts[index:] == 'branch list'.split())


@git_support
def get_new_command(command):
    return shell.and_('git branch --delete list', 'git branch')
