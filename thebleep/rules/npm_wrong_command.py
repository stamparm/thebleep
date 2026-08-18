import re
from thebleep.specific.npm import npm_available
from thebleep.utils import replace_argument, for_app, eager, get_closest
from thebleep.specific.sudo import sudo_support

enabled_by_default = npm_available

# npm 6 and earlier answered an unknown command by listing every command they
# knew; npm 7 and later name the one they think you meant.
SUGGESTION = re.compile(r'^\s+npm ([^\s#]+)')


def _get_wrong_command(script_parts):
    commands = [part for part in script_parts[1:] if not part.startswith('-')]
    if commands:
        return commands[0]


@eager
def _suggested_commands(output):
    """The commands npm itself put forward, if it put any forward."""
    after_marker = False
    for line in output.split('\n'):
        if line.startswith('Did you mean'):
            after_marker = True
            continue
        if not after_marker:
            continue

        suggestion = SUGGESTION.match(line)
        if suggestion:
            yield suggestion.group(1)
        elif line.strip():
            # The suggestions are over: what follows is npm telling you how to
            # list them all, which is not a suggestion.
            break


@sudo_support
@for_app('npm')
def match(command):
    return (('where <command> is one of:' in command.output
             or 'Unknown command:' in command.output)
            and _get_wrong_command(command.script_parts))


@eager
def _get_available_commands(stdout):
    commands_listing = False
    for line in stdout.split('\n'):
        if line.startswith('where <command> is one of:'):
            commands_listing = True
        elif commands_listing:
            if not line:
                break

            for command in line.split(', '):
                stripped = command.strip()
                if stripped:
                    yield stripped


@sudo_support
def get_new_command(command):
    wrong_command = _get_wrong_command(command.script_parts)

    suggested = _suggested_commands(command.output)
    if suggested:
        return [replace_argument(command.script, wrong_command, suggestion)
                for suggestion in suggested]

    npm_commands = _get_available_commands(command.output)
    fixed = get_closest(wrong_command, npm_commands)
    return replace_argument(command.script, wrong_command, fixed)
