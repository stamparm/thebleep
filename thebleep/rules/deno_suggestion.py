# -*- encoding: utf-8 -*-

"""`deno runn` -> `deno run`, for the Deno JavaScript/TypeScript runtime.

Deno is a secure runtime for JavaScript and TypeScript. When a subcommand is
unrecognized, Deno suggests what it thinks you meant:

    $ deno runn
    error: Unrecognized subcommand 'runn'
    Did you mean 'run'?

    $ deno chekc
    error: Unrecognized subcommand 'chekc'
    Did you mean 'check'?

    $ deno fmtt
    error: Unrecognized subcommand 'fmtt'
    Did you mean 'fmt'?

Wordings captured from Deno 2.0.0.

"""

import re
from thebleep.utils import replace_command
from thebleep.utils import for_app

# Deno reports unknown subcommands with this pattern:
# error: Unrecognized subcommand 'runn'
UNKNOWN_SUBCOMMAND = re.compile(r"Unrecognized subcommand '([^']+)'")

# Deno suggestions:
# Did you mean 'run'?
SUGGESTION = re.compile(r"Did you mean '([^']+)'")

# Fast string literals for rule pack indexing
MARKERS = ('Unrecognized subcommand', 'Did you mean')


def _broken(output):
    """The word Deno did not recognise."""
    found = UNKNOWN_SUBCOMMAND.search(output)
    return found.group(1) if found else None


def _suggestions(output):
    """The names Deno offered, in the order it offered them."""
    found = SUGGESTION.search(output)
    if found:
        return [found.group(1)]
    return []


@for_app('deno')
def match(command):
    return ('Unrecognized subcommand' in command.output
            and 'Did you mean' in command.output
            and bool(_broken(command.output))
            and bool(_suggestions(command.output)))


def get_new_command(command):
    return replace_command(command, _broken(command.output),
                           _suggestions(command.output))
