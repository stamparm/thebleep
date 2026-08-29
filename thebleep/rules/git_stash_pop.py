from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 2] == ['stash', 'pop']
            and 'Your local changes to the following files would be overwritten by merge' in command.output)


@git_support
def get_new_command(command):
    return shell.and_('git add --update', 'git stash pop', 'git reset .')


# make it come before the other applicable rules
priority = 900
