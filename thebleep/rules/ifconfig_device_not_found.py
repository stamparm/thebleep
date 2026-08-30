import re

from thebleep.utils import (command_word_index, for_app, replace_command,
                            eager, tool_lines)


LINUX_NOT_FOUND = re.compile(
    r'^(\S+): error fetching interface information: Device not found')
BSD_NOT_FOUND = re.compile(
    r'^ifconfig: interface (\S+) does not exist')


@for_app('ifconfig')
def match(command):
    return (LINUX_NOT_FOUND.search(command.output) is not None
            or BSD_NOT_FOUND.search(command.output) is not None)


@eager
def _get_possible_interfaces():
    for line in tool_lines(['ifconfig', '-a']):
        if line and not line.startswith(' '):
            yield line.split(' ')[0]


def get_new_command(command):
    found = (LINUX_NOT_FOUND.search(command.output)
             or BSD_NOT_FOUND.search(command.output))
    if not found:
        return []
    interface = _typed_interface(command, found.group(1))
    possible_interfaces = _get_possible_interfaces()
    return replace_command(command, interface, possible_interfaces)


def _typed_interface(command, reported):
    """Use the complete operand when Linux shortened it in its diagnostic."""
    start = command_word_index(command.script_parts)
    for part in command.script_parts[start + 1:]:
        if not part.startswith('-') and part.startswith(reported):
            return part
    return reported
