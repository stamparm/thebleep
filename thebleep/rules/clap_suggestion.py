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

And there is a third shape, which is why the broken word is not always read out
of the message. deno 2.1 stopped echoing it:

    $ deno runn
    error: unrecognized subcommand

      tip: a similar subcommand exists: 'run'

The tip still names the answer, so the only question left is *what* to replace,
and that is on the command line the user typed: the first word after the
program that is not an option. Picking a nested dispatcher's word by mistake
costs nothing -- the closeness filter between that word and the names in the
tip comes back empty, and the rule offers nothing rather than nonsense.

Wordings captured from ruff 0.14.5, uv 0.12.5, cargo 1.97.1 and deno 2.1.4.

"""

import re
from thebleep.utils import command_word_index, replace_command

# What clap says it did not recognise. A subcommand is quoted plainly; an
# argument keeps its dashes, which is what makes the replacement land on the
# flag rather than on a word of the command. The quotes are optional: deno 2.1
# names nothing at all, and the word comes off the command line instead.
BROKEN = re.compile(r"error: (?:unrecognized subcommand|unexpected argument)"
                    r"(?: '([^']+)')?")

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

# cargo's own wording for the same thing, in backticks -- and its older ones.
# `no such subcommand` and `Did you mean \`x\`` are what cargo said before 1.73,
# and are kept so that retiring the hand-written `cargo_no_command` loses
# nothing. That rule also took the broken word from `script_parts[1]`, which is
# the second word of the command rather than the word cargo complained about, so
# `cargo --offline instal` was beyond it. Reading the name out of the message
# works wherever it sits.
CARGO_BROKEN = re.compile(r'error: no such (?:sub)?command:? `?([^`\s]+)`?')
CARGO_TIP = re.compile(
    r'(?:help: a command with a similar name exists|Did you mean):? '
    r'`([^`]+)`')


def _broken(command):
    """The word clap could not read, wherever it is named.

    The message names it when it names it at all; otherwise it is the first
    word of the command after the program that is not an option, which is
    where a subcommand sits. See the deno capture above for the shape that
    taught this.

    """
    found = BROKEN.search(command.output) or CARGO_BROKEN.search(command.output)
    # The bare deno shape *matches* `BROKEN`, with nothing captured -- so
    # "the regex found it" and "it named the word" are different questions.
    if found and found.group(1):
        return found.group(1)

    start = command_word_index(command.script_parts)
    for part in command.script_parts[start + 1:]:
        if not part.startswith('-'):
            return part


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
             or 'a command with a similar name exists' in command.output
             or 'no such subcommand' in command.output)
            and bool(_broken(command))
            and bool(_suggestions(command.output)))


def get_new_command(command):
    return replace_command(command, _broken(command),
                           _suggestions(command.output))
