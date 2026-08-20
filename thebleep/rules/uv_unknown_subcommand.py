# -*- encoding: utf-8 -*-

"""`uv piip install requests` -> `uv pip install requests`.

uv names the subcommand it did not recognise, and offers the ones it thinks
you meant when any of them is close enough:

    error: unrecognized subcommand 'piip'

      tip: a similar subcommand exists: 'pip'

    Usage: uv [OPTIONS] <COMMAND>

The wording is singular or plural according to how many it found, and there is
often more than one:

    error: unrecognized subcommand 're'

      tip: some similar subcommands exist: 'remove', 'tree'

A subcommand of a subcommand -- `uv pip instll`, `uv tool runn`,
`uv python instal` -- prints the same block, naming only the word it choked on,
so the same reading works for all of them.

When nothing is close enough uv prints no tip at all, and then there is
nothing to suggest and this does not match.

"""

import re
from thebleep.utils import for_app, replace_command

UNRECOGNIZED = re.compile(r"error: unrecognized subcommand '([^']+)'")
TIP = re.compile(r'tip: (?:a similar subcommand exists'
                 r'|some similar subcommands exist):(.*)')


def _get_broken(output):
    found = UNRECOGNIZED.search(output)
    return found.group(1) if found else None


def _get_suggestions(output):
    """Subcommands uv offered, in the order it offered them.

    `.` does not match a newline, so the tip is read off its own line without
    having to split the output up first.

    """
    found = TIP.search(output)
    return re.findall(r"'([^']+)'", found.group(1)) if found else []


@for_app('uv', at_least=1)
def match(command):
    return ('unrecognized subcommand' in command.output
            and bool(_get_broken(command.output))
            and bool(_get_suggestions(command.output)))


def get_new_command(command):
    broken = _get_broken(command.output)
    suggestions = _get_suggestions(command.output)
    return replace_command(command, broken, suggestions)
