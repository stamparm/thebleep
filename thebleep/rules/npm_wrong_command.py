import re
from thebleep.specific.npm import npm_available
from thebleep.utils import replace_argument, for_app, eager, get_closest
from thebleep.specific.sudo import sudo_support
from thebleep.shells import shell

enabled_by_default = npm_available

# npm 6 and earlier answered an unknown command by listing every command they
# knew; npm 7 and later name the one they think you meant.
#
# The whole suggestion, not its first word. npm's answers are routinely more
# than one word -- `npm build` is answered with `npm run build # run the
# "build" package script` -- and taking one word out of that produced the
# suggestion `npm run`, which does not build anything. The trailing `# ...` is
# npm's own commentary and is dropped.
SUGGESTION = re.compile(r'^\s+npm\s+(.+?)(?:\s+#.*)?$')


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
        # Quoted, like every other value read out of a tool's output: the
        # result of this is handed back to the shell to be evaluated, and
        # `replace_argument` does not quote what it substitutes. A command name
        # needs no quotes and gets none -- `shell.quote` adds them only where
        # they change the meaning -- so this costs nothing and closes the path.
        return [replace_argument(command.script, wrong_command,
                                 shell.quote(suggestion))
                for suggestion in suggested]

    npm_commands = _get_available_commands(command.output)
    fixed = get_closest(wrong_command, npm_commands)
    if fixed is None:
        # npm 7 and later print no command listing, and when they have nothing
        # to suggest they print no suggestion either -- so there is nothing to
        # go on. `get_closest` returning `None` instead of raising was the fix
        # for a crash here; passing it on produced the literal suggestion
        # `npm None`, which is worse than saying nothing, because it looks like
        # an answer and cannot run.
        return []

    return replace_argument(command.script, wrong_command, shell.quote(fixed))
