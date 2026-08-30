from itertools import dropwhile, islice, takewhile

from thebleep.shells import shell
from thebleep.utils import (get_closest, replace_argument, for_app, which,
                            cache, tool_lines)


def get_golang_commands():
    # `go` with no arguments prints its usage on stderr.
    lines = [line.strip() for line in tool_lines(('go',), merge_stderr=True)]
    lines = dropwhile(lambda line: line != 'The commands are:', lines)
    lines = islice(lines, 2, None)
    lines = takewhile(lambda line: line, lines)
    return [line.split(' ')[0] for line in lines]


if which('go'):
    get_golang_commands = cache(which('go'))(get_golang_commands)


@for_app('go', at_least=1)
def match(command):
    return 'unknown command' in command.output


def get_new_command(command):
    closest_subcommand = get_closest(
        command.script_parts[1], get_golang_commands(),
        fallback_to_first=False)
    if closest_subcommand is None:
        return []
    return replace_argument(command.script, command.script_parts[1],
                            shell.quote(closest_subcommand))
