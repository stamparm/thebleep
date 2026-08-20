# -*- encoding: utf-8 -*-

"""`ruff chekc .` -> `ruff check .`, for any tool built with clap.

Not a rule about one program. clap is the argument parser most Rust command
line tools are written with, and when it does not recognise a word it prints
what it thinks you meant, in a shape that does not vary:

    $ ruff chekc .
    error: unrecognized subcommand 'chekc'

      tip: a similar subcommand exists: 'check'

    $ ruff check --fixx .
    error: unexpected argument '--fixx' found

      tip: a similar argument exists: '--fix'

    $ uv re
    error: unrecognized subcommand 're'

      tip: some similar subcommands exist: 'remove', 'tree'

So this reads clap rather than reading a tool, and every clap program is
corrected by it -- `uv`, `ruff`, `rustup`, `fd`, `bat`, `hyperfine`, and
whatever is written next -- with nothing added here for any of them. The
alternative, which is where this project started, is one rule per tool, written
after somebody notices the tool exists, and then left to rot when its wording
changes: seven such rules were found dead in a single afternoon.

`cargo` is here too. It is a clap program that words the same thing its own way:

    $ cargo instal ripgrep
    error: no such command: `instal`

    help: a command with a similar name exists: `install`

**Options are corrected as well as subcommands**, which nothing did before. A
mistyped flag is at least as common as a mistyped subcommand and clap hands you
the answer for both.

Wordings captured from ruff 0.14.5, uv 0.12.5 and cargo 1.97.1.

"""

import re
from thebleep.utils import replace_command

# What clap says it did not recognise. A subcommand is quoted plainly; an
# argument keeps its dashes, which is what makes the replacement land on the
# flag rather than on a word of the command.
BROKEN = re.compile(r"error: (?:unrecognized subcommand|unexpected argument) "
                    r"'([^']+)'")

# Singular and plural, subcommand and argument, all four in one:
#
#   tip: a similar subcommand exists: 'check'
#   tip: some similar subcommands exist: 'remove', 'tree'
#   tip: a similar argument exists: '--fix'
#
# `.` does not match a newline, so the tip is read off its own line without
# splitting the output up first.
TIP = re.compile(r'tip: (?:a similar (?:subcommand|argument) exists'
                 r'|some similar (?:subcommands|arguments) exist):(.*)')

# cargo's own wording for the same thing, in backticks.
CARGO_BROKEN = re.compile(r'error: no such command: `([^`]+)`')
CARGO_TIP = re.compile(r'help: a command with a similar name exists: '
                       r'`([^`]+)`')

# Enough of the wording to tell the rule pack when this cannot possibly apply,
# so it is not loaded for every correction. `for_app` is deliberately absent --
# the whole point is that the program is not known in advance.
MARKERS = ('tip: a similar', 'tip: some similar',
           'a command with a similar name exists')


def _broken(output):
    found = BROKEN.search(output) or CARGO_BROKEN.search(output)
    return found.group(1) if found else None


def _suggestions(output):
    """The names clap offered, in the order it offered them."""
    found = TIP.search(output)
    if found:
        return re.findall(r"'([^']+)'", found.group(1))

    found = CARGO_TIP.search(output)
    return [found.group(1)] if found else []


def match(command):
    return (('tip: a similar' in command.output
             or 'tip: some similar' in command.output
             or 'a command with a similar name exists' in command.output)
            and bool(_broken(command.output))
            and bool(_suggestions(command.output)))


def get_new_command(command):
    return replace_command(command, _broken(command.output),
                           _suggestions(command.output))
