# -*- encoding: utf-8 -*-

"""`pytest --color=ayt` -> `pytest --color=auto`. Python argparse choices.

Any tool built with Python's standard library `argparse` module prints the
value it did not recognize and every value it does:

    $ python -m pytest --color=ayt
    python -m pytest: error: argument --color: invalid choice: 'ayt' (choose from 'yes', 'no', 'auto')

    $ mytool bulid
    mytool: error: argument sub: invalid choice: 'bulid' (choose from 'install', 'build', 'check')

    $ mytool --color ayt
    mytool: error: argument --color/-c: invalid choice: 'ayt' (choose from 'yes', 'no', 'auto')

The choices are quoted, and an option with a short alias is named as
`--color/-c` -- both of which the pattern below has to allow for, and neither of
which was in the output this rule was first written against.

This covers `pytest`, `mypy`, `pipx`, `pre-commit`, `tox`, `coverage`, and every
other Python CLI built with `argparse`.

The choices list is ordered by Damerau-Levenshtein distance to the typo using
`thebleep.matching.order`, and the replacement is shell-quoted.

Captured from argparse on Python 3.9, 3.11, 3.12, 3.13 and 3.14 --
the wording is the same on all of them -- and from pytest 9.1.1.

"""

import re
from thebleep import matching
from thebleep.utils import memoize, replace_value

# `error: argument --color: invalid choice: 'ayt' (choose from 'yes', 'no',
# 'auto')`. The choices are quoted on every Python from 3.9 to 3.14; the
# unquoted form is accepted too, in case a future one drops them, and because
# `argparse` is vendored and patched in more places than is comfortable.
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


def get_new_command(command):
    rejected, choices = _rejected_and_choices(command.output)
    # `replace_value` because `--format=yamll` glues the value to its option,
    # which `replace_argument` cannot see. It quotes, too: these names came out
    # of the program's own output. Shared with
    # `invalid_argument_for_option`, which reads gnulib's version of the same
    # message.
    return [replace_value(command.script, rejected, name)
            for name in matching.order(rejected, choices, limit=3)]
