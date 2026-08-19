from thebleep.shells import shell
from thebleep.specific.git import git_support


@git_support
def match(command):
    return 'help' in command.script and ' is aliased to ' in command.output


@git_support
def get_new_command(command):
    # The alias comes out of `.git/config`, so a repository you cloned chose it.
    aliased = command.output.split('`', 2)[2].split("'", 1)[0].split(' ', 1)[0]
    return 'git help {}'.format(shell.quote(aliased))
