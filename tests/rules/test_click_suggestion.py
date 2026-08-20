# -*- encoding: utf-8 -*-

"""One rule for every tool built with Click.

Captured from black 25.9.0 (Click 8.x). `black` has no rule of its own; it is
corrected because the rule reads Click.

"""

import pytest
from thebleep.rules.click_suggestion import match, get_new_command
from thebleep.types import Command

BLACK = (
    'Usage: black [OPTIONS] SRC ...\n'
    "Try 'black --help' for help.\n"
    '\n'
    "Error: No such option '--chekc'. (Did you mean one of: '--check', "
    "'--code', '--help'?)\n"
)

# Click 7 and older: a colon, and no quotes.
OLD_CLICK = (
    'Usage: tool [OPTIONS]\n'
    '\n'
    'Error: no such option: --chekc\n'
)

ONE_GUESS = (
    "Error: No such option '--verbse'. (Did you mean '--verbose'?)\n"
)

# Click names `--help` among its guesses. True, and never what was meant.
ONLY_HELP = (
    "Error: No such option '--zzz'. (Did you mean one of: '--help'?)\n"
)


class TestReadingClick(object):
    def test_the_option_is_corrected(self):
        assert get_new_command(
            Command('black --chekc .', BLACK))[0] == 'black --check .'

    def test_one_guess(self):
        assert get_new_command(
            Command('tool --verbse', ONE_GUESS))[0] == 'tool --verbose'

    def test_help_is_not_the_answer(self):
        """Nobody types `--chekc` meaning `--help`, so it is dropped -- unless
        it is all Click offered."""
        assert '--help' not in get_new_command(
            Command('black --chekc .', BLACK))[0]

    def test_unless_it_is_all_there_is(self):
        assert get_new_command(
            Command('tool --zzz', ONLY_HELP)) == ['tool --help']


class TestNotMatching(object):
    @pytest.mark.parametrize('script, output', [
        # Older Click names no alternatives, so there is nothing to offer.
        ('tool --chekc', OLD_CLICK),
        ('black .', ''),
        ('ruff chekc .', "  tip: a similar subcommand exists: 'check'\n"),
    ])
    def test_it_says_nothing(self, script, output):
        assert not match(Command(script, output))


def test_a_suggestion_is_quoted():
    hostile = BLACK.replace("'--check'", "'--check;>PWNED'")
    suggestions = get_new_command(Command('black --chekc .', hostile))
    assert "black '--check;>PWNED' ." in suggestions
