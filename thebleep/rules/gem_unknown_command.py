import re
from thebleep.utils import (for_app, eager, replace_command, cache, which,
                            tool_lines)


@for_app('gem')
def match(command):
    # RubyGems raised Gem::CommandLineError for this until 3.2 and
    # Gem::UnknownCommandError since, so the class name is no help.
    return ('ERROR:  While executing gem ...' in command.output
            and 'Unknown command' in command.output)


def _get_unknown_command(command):
    return re.findall(r'Unknown command (\S+)', command.output)[0]


@eager
def _get_all_commands():
    for line in tool_lines(['gem', 'help', 'commands']):
        # A command is indented by four spaces. A description that wrapped is
        # indented much further, and was being taken for a command of its own:
        # `gem help commands` on RubyGems 3.4 wraps four of them, which is
        # where `located`, `for` and a bare URL came into the suggestions.
        if line.startswith('    ') and not line.startswith('     '):
            yield line.strip().split(' ')[0]


if which('gem'):
    _get_all_commands = cache(which('gem'))(_get_all_commands)


def get_new_command(command):
    unknown_command = _get_unknown_command(command)
    all_commands = _get_all_commands()
    return replace_command(command, unknown_command, all_commands)
