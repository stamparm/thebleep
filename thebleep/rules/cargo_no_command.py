import re
from thebleep.utils import replace_argument, for_app

# cargo said `no such subcommand` and `Did you mean \`build\`?` up to 1.72; it
# now says `no such command` and puts the suggestion in a `help:` line.
SUGGESTION = re.compile(
    r'(?:Did you mean|a command with a similar name exists:) `([^`]*)`')


@for_app('cargo', at_least=1)
def match(command):
    lowered = command.output.lower()
    return (('no such subcommand' in lowered or 'no such command' in lowered)
            and SUGGESTION.search(command.output) is not None)


def get_new_command(command):
    broken = command.script_parts[1]
    fix = SUGGESTION.search(command.output).group(1)

    return replace_argument(command.script, broken, fix)
