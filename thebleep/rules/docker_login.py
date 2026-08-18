from thebleep.utils import for_app
from thebleep.shells import shell


@for_app('docker')
def match(command):
    # `for_app` has already established that this is docker; asking whether the
    # word appears in the script as well would only add ways to be wrong.
    return ("access denied" in command.output
            and "may require 'docker login'" in command.output)


def get_new_command(command):
    return shell.and_('docker login', command.script)
