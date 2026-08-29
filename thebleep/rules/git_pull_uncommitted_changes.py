from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['pull']
            and ('You have unstaged changes' in command.output
                 or 'contains uncommitted changes' in command.output))


@git_support
def get_new_command(command):
    return shell.and_('git stash', 'git pull', 'git stash pop')
