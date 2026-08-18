import re
from thebleep.utils import for_app, which, replace_argument


def _get_command_name(command):
    found = re.findall(r'sudo: (.*): command not found', command.output)
    if found:
        return found[0]


@for_app('sudo')
def match(command):
    if 'command not found' in command.output:
        # sudo says this about things other than a missing program, and then
        # there is no name to look up: `which(None)` raises TypeError.
        command_name = _get_command_name(command)
        return bool(command_name) and bool(which(command_name))


def get_new_command(command):
    command_name = _get_command_name(command)
    return replace_argument(command.script, command_name,
                            u'env "PATH=$PATH" {}'.format(command_name))
