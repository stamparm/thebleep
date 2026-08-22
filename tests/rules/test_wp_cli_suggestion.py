# -*- encoding: utf-8 -*-

"""Captured from wordpress:cli, WP-CLI 2.12, by running the failing command."""

import pytest

from thebleep.rules.wp_cli_suggestion import match, get_new_command
from thebleep.types import Command

PLUGIN = (
    'Error: \'plugn\' is not a registered wp command. '
    "See 'wp help' for available commands.\n"
    "Did you mean 'plugin'?\n"
)
EVAL = (
    "Warning: No WordPress installation found. If the command 'evaal 1+1' is "
    'in a plugin or theme, pass --path=`path/to/wordpress`.\n'
    "Error: 'evaal' is not a registered wp command. "
    "See 'wp help' for available commands.\n"
    "Did you mean 'eval'?\n"
)

# Nothing close enough for wp to name an answer.
NO_MEANING = (
    "Error: 'zzzzzz' is not a registered wp command. "
    "See 'wp help' for available commands.\n"
)


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('wp plugn list', PLUGIN),
        ('wp evaal 1+1', EVAL),
    ])
    def test_wp_named_what_it_meant(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('wp zzzzzz', NO_MEANING),
        # composer's wording, which a different rule reads.
        ('wp install', 'Command "instal" is not defined.\n'),
    ])
    def test_otherwise_it_says_nothing(self, script, output):
        assert not match(Command(script, output))


def test_the_suggestion_comes_from_the_message():
    assert get_new_command(Command('wp plugn list', PLUGIN)) == 'wp plugin list'


def test_the_rest_of_the_command_survives():
    assert get_new_command(Command('wp evaal 1+1', EVAL)) == 'wp eval 1+1'


def test_a_suggestion_is_quoted():
    """The name is read out of output and goes back to a shell. See
    `tests/test_injection.py`."""
    hostile = PLUGIN.replace("'plugin'", "'plugin;>PWNED'")
    assert get_new_command(Command('wp plugn list', hostile)) == \
        "wp 'plugin;>PWNED' list"
