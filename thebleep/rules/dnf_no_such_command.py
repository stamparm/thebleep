import re
from thebleep.specific.sudo import sudo_support
from thebleep.utils import for_app, replace_command, tool_output
from thebleep.specific.dnf import dnf_available


regex = re.compile(r'No such command: (.*)\.')


@sudo_support
@for_app('dnf')
def match(command):
    return 'no such command' in command.output.lower()


def _parse_operations(help_text_lines):
    operation_regex = re.compile(r'^([a-z-]+) +', re.MULTILINE)
    return operation_regex.findall(help_text_lines)


def _get_operations():
    return _parse_operations(tool_output(['dnf', '--help']))


@sudo_support
def get_new_command(command):
    misspelled_command = regex.findall(command.output)[0]
    return replace_command(command, misspelled_command, _get_operations())


enabled_by_default = dnf_available
