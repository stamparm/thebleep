# -*- encoding: utf-8 -*-

"""One rule for every tool built with clap, and the fixtures prove it.

Captured from ruff 0.14.5, uv 0.12.5 and cargo 1.97.1 by running the failing
command. `ruff` and `rustup` have no rule of their own anywhere in this project,
which is the point: the rule reads the framework, so a tool nobody has written a
rule for is corrected anyway.

"""

import pytest
from thebleep.rules.clap_suggestion import match, get_new_command
from thebleep.types import Command

# ruff 0.14.5, a tool with no rule of its own.
RUFF_SUBCOMMAND = (
    "error: unrecognized subcommand 'chekc'\n"
    "\n"
    "  tip: a similar subcommand exists: 'check'\n"
    "\n"
    'Usage: ruff [OPTIONS] <COMMAND>\n'
    "\n"
    "For more information, try '--help'.\n"
)
RUFF_OPTION = (
    "error: unexpected argument '--fixx' found\n"
    "\n"
    "  tip: a similar argument exists: '--fix'\n"
    "\n"
    'Usage: ruff check --fix [FILES]...\n'
)
RUFF_LONG_OPTION = (
    "error: unexpected argument '--lin' found\n"
    "\n"
    "  tip: a similar argument exists: '--line-length'\n"
)

# uv 0.12.5, plural.
UV_MANY = (
    "error: unrecognized subcommand 're'\n"
    "\n"
    "  tip: some similar subcommands exist: 'remove', 'tree'\n"
    "\n"
    'Usage: uv [OPTIONS] <COMMAND>\n'
)

# deno 2.1.4, which colours its error even when nothing is watching and no
# longer echoes the word it choked on. The escapes are what a rule receives;
# captured piped, with no NO_COLOR set.
DENO_COLOURED = (
    '\x1b[0m\x1b[1m\x1b[31merror\x1b[0m: unrecognized subcommand\n'
    '\n'
    "  tip: a similar subcommand exists: 'run'\n"
)

# The same shape without the colour, and with several candidates.
DENO_MANY = (
    'error: unrecognized subcommand\n'
    '\n'
    "  tip: some similar subcommands exist: 'init', 'lint', 'uninstall', "
    "'install'\n"
)

# cargo 1.97.1, which words it its own way, in backticks.
CARGO = (
    'error: no such command: `instal`\n'
    '\n'
    'help: a command with a similar name exists: `install`\n'
    '\n'
    'help: view all installed commands with `cargo --list`\n'
)

# cargo before 1.73, from the fixtures of the `cargo_no_command` rule this
# replaces. Kept so that retiring it loses nothing.
CARGO_OLD = (
    'error: no such subcommand: `buid`\n'
    '\n'
    '\tDid you mean `build`?\n'
)

# Nothing close enough, so clap offers no tip and there is nothing to read.
NO_TIP = (
    "error: unrecognized subcommand 'zzzzzz'\n"
    "\n"
    'Usage: ruff [OPTIONS] <COMMAND>\n'
)


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('ruff chekc .', RUFF_SUBCOMMAND),
        ('ruff check --fixx .', RUFF_OPTION),
        ('uv re', UV_MANY),
        ('cargo instal ripgrep', CARGO),
        ('cargo buid', CARGO_OLD),
    ])
    def test_a_tip_is_there_to_read(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('ruff zzzzzz', NO_TIP),
        ('ruff check .', ''),
        # Somebody else's error, with no tip in it.
        ('helm instal x', 'Error: unknown command "instal" for "helm"\n'),
    ])
    def test_otherwise_it_says_nothing(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    @pytest.mark.parametrize('script, output, expected', [
        ('ruff chekc .', RUFF_SUBCOMMAND, 'ruff check .'),
        ('cargo instal ripgrep', CARGO, 'cargo install ripgrep'),
        ('cargo buid', CARGO_OLD, 'cargo build'),
    ])
    def test_a_subcommand(self, script, output, expected):
        assert get_new_command(Command(script, output))[0] == expected

    @pytest.mark.parametrize('script, output, expected', [
        ('ruff check --fixx .', RUFF_OPTION, 'ruff check --fix .'),
        ('ruff check --lin', RUFF_LONG_OPTION, 'ruff check --line-length'),
    ])
    def test_an_option_too(self, script, output, expected):
        """Nothing corrected a mistyped *flag* before this, and clap names the
        answer for one exactly as it does for a subcommand."""
        assert get_new_command(Command(script, output))[0] == expected

    def test_several_are_offered_closest_first(self):
        assert get_new_command(Command('uv re', UV_MANY)) == [
            'uv tree', 'uv remove']

    def test_the_word_is_taken_from_the_command_when_clap_names_nothing(self):
        """deno 2.1 stopped echoing it; the tip still names the answer."""
        assert match(Command('deno runn', DENO_COLOURED))
        assert get_new_command(Command('deno runn', DENO_COLOURED)) == \
            ['deno run']

    def test_the_colour_does_not_hide_any_of_it(self):
        """The reset between `error` and its colon used to hide the whole
        message from this rule -- see 4.0.4."""
        assert get_new_command(Command('deno instal', DENO_MANY))[0] == \
            'deno install'

    def test_the_rest_of_the_command_survives(self):
        assert get_new_command(
            Command('ruff chekc --no-cache src/', RUFF_SUBCOMMAND))[0] == \
            'ruff check --no-cache src/'

    def test_a_suggestion_is_quoted(self):
        """The name is read out of output and the result goes to a shell.
        See `tests/test_injection.py`."""
        hostile = RUFF_SUBCOMMAND.replace("'check'", "'check;>PWNED'")
        suggestions = get_new_command(Command('ruff chekc .', hostile))
        assert "ruff 'check;>PWNED' ." in suggestions
        assert 'ruff check;>PWNED .' not in suggestions


def test_the_broken_word_comes_from_the_message_not_the_position():
    """`cargo_no_command`, which this replaces, took `script_parts[1]` -- the
    second word of the command rather than the word cargo complained about -- so
    a global option in front of the subcommand defeated it."""
    assert get_new_command(
        Command('cargo --offline instal ripgrep', CARGO))[0] == \
        'cargo --offline install ripgrep'


def test_a_subcommand_of_a_subcommand():
    """`uv pip instll`, from the `uv_unknown_subcommand` rule this replaces:
    clap names only the word it choked on, so the same reading works."""
    output = ("error: unrecognized subcommand 'instll'\n\n"
              "  tip: some similar subcommands exist: 'list', 'uninstall', "
              "'install'\n\n"
              'Usage: uv pip [OPTIONS] <COMMAND>\n')
    assert get_new_command(Command('uv pip instll requests', output))[0] == \
        'uv pip install requests'
