from thebleep.specific.apt import apt_available
from thebleep.specific.sudo import sudo_support
from thebleep.utils import (command_word_index, for_app, eager,
                            replace_argument, replace_command, tool_lines)

enabled_by_default = apt_available


# apt-get says `E: Invalid operation instal`; apt 3.0 -- Debian trixie, Ubuntu
# 25.04 and newer -- says `Error: Invalid operation instal`. Only the first was
# matched, so `apt instal vim` got nothing while `apt-get instal vim` worked,
# and `apt` is the one people type. Both captured from the real programs.
INVALID_OPERATION = 'Invalid operation'


@sudo_support
@for_app('apt', 'apt-get', 'apt-cache')
def match(command):
    return INVALID_OPERATION in command.output


@eager
def _parse_apt_operations(help_text_lines):
    is_commands_list = False
    for line in help_text_lines:
        line = line.strip()
        if is_commands_list and line:
            yield line.split()[0]
        elif line.startswith('Basic commands:') \
                or line.startswith('Most used commands:'):
            is_commands_list = True


@eager
def _parse_apt_get_and_cache_operations(help_text_lines):
    is_commands_list = False
    for line in help_text_lines:
        line = line.strip()
        if is_commands_list:
            if not line:
                return

            yield line.split()[0]
        elif line.startswith('Commands:') \
                or line.startswith('Most used commands:'):
            is_commands_list = True


def _get_operations(app):
    lines = tool_lines([app, '--help'])

    if app == 'apt':
        return _parse_apt_operations(lines)
    else:
        return _parse_apt_get_and_cache_operations(lines)


@sudo_support
def get_new_command(command):
    invalid_operation = command.output.split()[-1]

    if invalid_operation == 'uninstall':
        return [replace_argument(command.script, 'uninstall', 'remove')]

    else:
        start = command_word_index(command.script_parts)
        operations = _get_operations(command.script_parts[start])
        return replace_command(command, invalid_operation, operations)
