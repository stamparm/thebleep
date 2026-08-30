# -*- encoding: utf-8 -*-

"""`prettier --chekc .` -> `prettier --check .`, for any tool built with commander.js.

The fourth of the framework rules, after `clap_suggestion`,
`cobra_suggestion` and `click_suggestion`. Commander is what most Node.js and
JavaScript command line tools are written with, and when it encounters an
unknown command or option, it suggests what it thinks you meant:

    $ mytool bulid
    error: unknown command 'bulid'
    (Did you mean build?)

    $ mytool tet
    error: unknown command 'tet'
    (Did you mean one of test, text?)

    $ prettier --chekc .
    error: unknown option '--chekc'
    (Did you mean --check?)

    $ mytool --tet
    error: unknown option '--tet'
    (Did you mean one of --test, --text?)

So `prettier`, `eslint`, `prisma`, `nest`, `turbo`, `webpack-cli`, `ts-node`,
`create-react-app` and the rest come free with nothing added here for any of them.

Captured from commander 13.1.0.

"""

import re
from thebleep.types import Suggestion
from thebleep.utils import replace_command

# The command or option Commander did not recognise.
BROKEN = re.compile(r"error: unknown (?:command|option) '([^']+)'")

# The suggestion line: `(Did you mean build?)` or `(Did you mean one of test, text?)`.
DID_YOU_MEAN = re.compile(
    r"\(?[Dd]id you mean (?:one of )?([^\r\n?]+)\)?\??")


def _broken(output):
    found = BROKEN.search(output)
    return found.group(1) if found else None


def _suggestions(output):
    """The names Commander offered, in the order it offered them."""
    found = DID_YOU_MEAN.search(output)
    if not found:
        return []

    raw = found.group(1).rstrip(')').strip()
    return [s.strip() for s in raw.split(',') if s.strip()]


def match(command):
    # Rulepack can extract literal string checks.
    return (('unknown command' in command.output
             or 'unknown option' in command.output)
            and 'id you mean' in command.output
            and bool(_broken(command.output))
            and bool(_suggestions(command.output)))


def get_new_command(command):
    return [Suggestion(fixed, confidence=0.98, evidence=(
        'commander named this replacement in the command error',))
        for fixed in replace_command(command, _broken(command.output),
                                     _suggestions(command.output))]
