from thebleep.shells import shell
from thebleep.utils import for_app


@for_app('terraform')
def match(command):
    if 'init' in command.script_parts:
        return False

    output = command.output.lower()
    # Terraform has worded the error differently for each way a working
    # directory can be uninitialised -- a module it has not installed, a
    # provider version it has not selected or not cached, a backend it has not
    # configured -- and has added wordings since. What it does in all of them
    # is name the remedy.
    return ('this module is not yet installed' in output
            or 'initialization required' in output
            or 'terraform init' in output)


def get_new_command(command):
    return shell.and_('terraform init', command.script)
