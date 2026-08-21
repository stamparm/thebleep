# -*- encoding: utf-8 -*-

"""`pytest --color=ayt` -> `pytest --color=auto`. Python argparse choices.

Any tool built with Python's standard library `argparse` module prints the
value it did not recognize and every value it does:

    $ python -m pytest --color=ayt
    python.exe -m pytest: error: argument --color: invalid choice: 'ayt' (choose from yes, no, auto)

    $ mytool bulid
    mytool: error: argument sub: invalid choice: 'bulid' (choose from install, build, check)

    $ pre-commit runn
    pre-commit: error: argument hook: invalid choice: 'runn' (choose from run, clean, autoupdate)

This covers `pytest`, `mypy`, `pipx`, `pre-commit`, `tox`, `coverage`, and every
other Python CLI built with `argparse`.

The choices list is ordered by Damerau-Levenshtein distance to the typo using
`thebleep.matching.order`, and the replacement is shell-quoted.

Captured from Python 3.12 / 3.14 argparse and pytest 8.x/9.x.

"""

import re
from thebleep import matching
from thebleep.shells import shell
from thebleep.utils import memoize, replace_argument

# `error: argument --color: invalid choice: 'ayt' (choose from yes, no, auto)`
# or with quotes: `(choose from 'install', 'build', 'check')`.
INVALID_CHOICE = re.compile(
    r"error: argument (?:[^\s:]+): invalid choice: '([^']*)' \(choose from ([^)]+)\)")


@memoize
def _rejected_and_choices(output):
    """`(rejected_value, [valid_choices])` or `None`."""
    found = INVALID_CHOICE.search(output)
    if not found:
        return None

    rejected = found.group(1)
    raw_choices = found.group(2)
    choices = [c.strip().strip("'\"") for c in raw_choices.split(',') if c.strip()]
    if not choices:
        return None

    return rejected, choices


def match(command):
    # Rulepack can extract literal string checks.
    return ('invalid choice:' in command.output
            and 'choose from' in command.output
            and _rejected_and_choices(command.output) is not None)


def _with(script, rejected, name):
    """`script` with the rejected value replaced by `name`."""
    quoted = shell.quote(name)

    glued = u'={}'.format(rejected)
    if glued in script:
        return script.replace(glued, u'={}'.format(quoted), 1)

    return replace_argument(script, rejected, quoted)


def get_new_command(command):
    rejected, choices = _rejected_and_choices(command.output)
    return [_with(command.script, rejected, name)
            for name in matching.order(rejected, choices, limit=3)]
