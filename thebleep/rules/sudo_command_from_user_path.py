import re
from thebleep.shells import shell
from thebleep.utils import for_app, raw_script_parts, which


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
    parts = command.script_parts
    raw_parts = raw_script_parts(command.script)
    if len(parts) != len(raw_parts):
        return []

    for index, part in enumerate(parts[1:], 1):
        if part == command_name:
            raw_parts[index] = u'env "PATH=$PATH" {}'.format(
                shell.quote(command_name))
            return u' '.join(raw_parts)

    return []
