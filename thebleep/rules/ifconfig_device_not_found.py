from thebleep.utils import for_app, replace_command, eager, tool_lines


@for_app('ifconfig')
def match(command):
    return 'error fetching interface information: Device not found' \
           in command.output


@eager
def _get_possible_interfaces():
    for line in tool_lines(['ifconfig', '-a']):
        if line and not line.startswith(' '):
            yield line.split(' ')[0]


def get_new_command(command):
    interface = command.output.split(' ')[0][:-1]
    possible_interfaces = _get_possible_interfaces()
    return replace_command(command, interface, possible_interfaces)
