import re
from thebleep.specific.sudo import sudo_support
from thebleep.utils import for_app, replace_command, tool_output
from thebleep.specific.dnf import dnf_available


# dnf 4: `No such command: isntall. Please use /usr/bin/dnf --help`.
# dnf 5, Fedora 41 and later: `Unknown argument "isntall" for command "dnf5".`
# Both captured from the real programs; the first was the only one matched,
# so every current Fedora got nothing.
regex = re.compile(r'No such command: (.*?)\.|Unknown argument "([^"]+)"')


@sudo_support
@for_app('dnf', 'dnf5')
def match(command):
    output = command.output.lower()
    return 'no such command' in output or 'unknown argument' in output


def _parse_operations(help_text_lines):
    # dnf 4 lists its commands at the start of the line; dnf 5 indents them
    # under group headings. A heading ends in a colon, so it is not a match.
    operation_regex = re.compile(r'^ *([a-z][a-z0-9-]*) {2,}\S', re.MULTILINE)
    return operation_regex.findall(help_text_lines)


def _get_operations():
    return _parse_operations(tool_output(['dnf', '--help']))


@sudo_support
def get_new_command(command):
    found = regex.search(command.output)
    if not found:
        return []
    broken = found.group(1) or found.group(2)
    return replace_command(command, broken, _get_operations())


enabled_by_default = dnf_available
