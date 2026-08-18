from thebleep.utils import for_app
from thebleep.specific.sudo import sudo_support


@sudo_support
@for_app('pip', 'pip2', 'pip3')
def match(command):
    return ('install' in command.script_parts
            and '--user' not in command.script_parts
            and 'Permission denied' in command.output)


def get_new_command(command):
    # `--user` and nothing else.
    #
    # When `--user` had already been tried this used to fall back to
    # `sudo pip install ...`, which is the one thing not to suggest: it writes
    # into the interpreter the operating system maintains, where it can leave
    # the package manager's idea of what is installed and reality disagreeing,
    # and it hands a package's own setup code root. Nothing here can be sure a
    # correction is the right moment to do that, so there is no second attempt
    # -- an environment where even `--user` cannot write wants a virtualenv or
    # pipx, which is a decision and not a one-line fix.
    return command.script.replace(' install ', ' install --user ')
