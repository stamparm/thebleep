from thebleep.specific.git import git_support
from thebleep.utils import remove_argument_sequence


@git_support
def match(command):
    return (' git clone ' in command.script
            and 'fatal: Too many arguments.' in command.output)


@git_support
def get_new_command(command):
    return remove_argument_sequence(command.script, ('git', 'clone'), start=2)
