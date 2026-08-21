# -*- encoding: utf-8 -*-

"""`bun runn` -> `bun run`, for the bun JavaScript runtime.

bun is a modern JavaScript runtime and package manager, a fast drop-in
replacement for Node.js and npm. When a command or script is unrecognized,
bun suggests what it thinks you meant:

    $ bun runn
    error: "runn" is not a recognized Bun command.
    Did you mean "run"?

    $ bun teest
    error: "teest" is not a recognized Bun command.
    Did you mean "test"?

    $ bun run buidl
    error: Script not found "buidl"
    Did you mean "build"?

Wordings captured from bun 1.1.0.

"""

import re
from thebleep.utils import replace_command
from thebleep.utils import for_app

# bun reports unknown commands with this pattern:
# error: "runn" is not a recognized Bun command.
UNKNOWN_COMMAND = re.compile(r'"([^"]+)" is not a recognized Bun command')

# bun reports missing scripts with:
# error: Script not found "buidl"
SCRIPT_NOT_FOUND = re.compile(r'Script not found "([^"]+)"')

# bun suggestions:
# Did you mean "run"?
SUGGESTION = re.compile(r'Did you mean "([^"]+)"\?')

# Fast string literals for rule pack indexing
MARKERS = ('is not a recognized Bun command', 'Script not found', 'Did you mean')


def _broken(output):
    """The word bun did not recognise."""
    found = UNKNOWN_COMMAND.search(output) or SCRIPT_NOT_FOUND.search(output)
    return found.group(1) if found else None


def _suggestions(output):
    """The names bun offered, in the order it offered them."""
    found = SUGGESTION.search(output)
    if found:
        return [found.group(1)]
    return []


@for_app('bun')
def match(command):
    return (('is not a recognized Bun command' in command.output
             or 'Script not found' in command.output)
            and 'Did you mean' in command.output
            and bool(_broken(command.output))
            and bool(_suggestions(command.output)))


def get_new_command(command):
    return replace_command(command, _broken(command.output),
                           _suggestions(command.output))
