# -*- encoding: utf-8 -*-

"""`uv piip install requests` -> `uv pip install requests`.

uv reports unrecognized subcommands and offers suggestions when a close
command exists:

    error: unrecognized subcommand 'piip'

      tip: a similar subcommand exists: 'pip'

When multiple subcommands match:

    error: unrecognized subcommand 're'

      tip: some similar subcommands exist: 'remove', 'tree'

Subcommands under namespaces (`uv pip instll`, `uv tool runn`) print the same
tip block naming the subcommand in question.

"""

import re
from thebleep.utils import for_app, replace_command

UNRECOGNIZED = re.compile(r"error: unrecognized subcommand '([^']+)'")
TIP = re.compile(
    r"tip: (?:a similar subcommand exists|some similar subcommands exist):\s*(.+)")


def _get_broken(output):
    found = UNRECOGNIZED.search(output)
    return found and found.group(1)


def _get_suggestions(output):
    """Subcommands uv offered, extracted from the tip line."""
    for line in output.split('\n'):
        found = TIP.search(line)
        if found:
            return re.findall(r"'([^']+)'", found.group(1))
    return []


@for_app('uv', at_least=1)
def match(command):
    return ('unrecognized subcommand' in command.output
            and bool(_get_broken(command.output))
            and bool(_get_suggestions(command.output)))


def get_new_command(command):
    broken = _get_broken(command.output)
    suggestions = _get_suggestions(command.output)
    return replace_command(command, broken, suggestions)
