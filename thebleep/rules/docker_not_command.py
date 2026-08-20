import re
from thebleep.utils import (replace_command, for_app, which, cache,
                            tool_lines)
from thebleep.specific.sudo import sudo_support

# Docker up to 19 said `docker: 'imge' is not a docker command.`; it now says
# `docker: unknown command: docker imge`, and for a management command it names
# the whole path, as in `docker: unknown command: docker image lss`.
UNKNOWN_COMMAND = re.compile(r'unknown command: docker ([^\r\n]+)')
NOT_A_COMMAND = re.compile(r"docker: '(\w+)' is not a docker command\.")

# Older docker separated `Usage:` from the command with a tab, newer with
# spaces.
USAGE = re.compile(r'Usage:\s+docker')


def _is_command_heading(line):
    """`Commands:`, and also `Common Commands:`, `Management Commands:` and
    `Swarm Commands:`, which is where docker now keeps most of what people
    type."""
    return line.endswith('Commands:') and not line.startswith((' ', '\t'))


def _parse_commands(lines):
    """Every command listed under any of a help text's command headings."""
    commands = []
    in_section = False
    for line in lines:
        line = line.rstrip('\r\n')
        if _is_command_heading(line):
            in_section = True
        elif not line.strip() or not line.startswith((' ', '\t')):
            # A blank or unindented line ends the listing, which is how
            # `Options:` and the rest of the help get left out.
            in_section = False
        elif in_section:
            commands.append(line.split()[0])

    return commands


def get_docker_commands(prefix=()):
    """What `docker <prefix>` accepts next, according to docker."""
    # Old versions of docker write their help to stdout, newer ones to
    # stderr, so both are read. Reading one and merely opening the other is
    # the deadlock: whichever docker did not choose fills up and blocks.
    return _parse_commands(
        tool_lines(('docker',) + tuple(prefix) + ('--help',),
                   merge_stderr=True))


if which('docker'):
    get_docker_commands = cache(which('docker'))(get_docker_commands)


def _listed_in_the_output(command):
    """Docker 19 to 24 answered an unknown subcommand of a management command
    with that command's usage, which lists what it does accept."""
    if not USAGE.search(command.output) or len(command.script_parts) < 3:
        return []

    return _parse_commands(command.output.split('\n'))


@sudo_support
@for_app('docker')
def match(command):
    return bool(NOT_A_COMMAND.search(command.output)
                or UNKNOWN_COMMAND.search(command.output)
                or _listed_in_the_output(command))


@sudo_support
def get_new_command(command):
    unknown = UNKNOWN_COMMAND.search(command.output)
    if unknown:
        parts = unknown.group(1).split()
        if parts:
            return replace_command(command, parts[-1],
                                   get_docker_commands(tuple(parts[:-1])))

    not_a_command = NOT_A_COMMAND.search(command.output)
    if not_a_command:
        return replace_command(command, not_a_command.group(1),
                               get_docker_commands())

    listed = _listed_in_the_output(command)
    if listed:
        return replace_command(command, command.script_parts[-1], listed)

    return []
