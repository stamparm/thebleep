from itertools import dropwhile, islice, takewhile

from thebleep.specific.sudo import sudo_support
from thebleep.specific.yum import yum_available
from thebleep.utils import (for_app, replace_command, which, cache,
                            tool_lines)

enabled_by_default = yum_available


@sudo_support
@for_app('yum')
def match(command):
    return 'No such command: ' in command.output


def _get_operations():
    lines = tool_lines(('yum',))
    lines = dropwhile(lambda line: not line.startswith("List of Commands:"), lines)
    lines = islice(lines, 2, None)
    lines = list(takewhile(lambda line: line.strip(), lines))
    return [line.strip().split(' ')[0] for line in lines]


if which('yum'):
    _get_operations = cache(which('yum'))(_get_operations)


@sudo_support
def get_new_command(command):
    invalid_operation = command.script_parts[1]

    if invalid_operation == 'uninstall':
        return [command.script.replace('uninstall', 'remove')]

    return replace_command(command, invalid_operation, _get_operations())
