import re

from thebleep.utils import for_app, replace_command, eager, tool_lines


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
    interface = found.group(1)
    possible_interfaces = _get_possible_interfaces()
    return replace_command(command, interface, possible_interfaces)
