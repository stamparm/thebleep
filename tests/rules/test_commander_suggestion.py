# -*- encoding: utf-8 -*-

"""One rule for every tool built with commander.js.

Captured from commander 13.1.0. `prettier`, `prisma` and `eslint` have no rule of
their own in this project; they are corrected because the rule reads commander
rather than reading a specific tool.

"""

import pytest
from thebleep.rules.commander_suggestion import match, get_new_command
from thebleep.types import Command

# Single command suggestion.
COMMAND_ONE = (
    "error: unknown command 'bulid'\n"
    "(Did you mean build?)\n"
)

# Multiple command suggestions.
COMMAND_MANY = (
    "error: unknown command 'tet'\n"
    "(Did you mean one of test, text?)\n"
)

# Single option suggestion.
OPTION_ONE = (
    "error: unknown option '--chekc'\n"
    "(Did you mean --check?)\n"
)

# Multiple option suggestions.
OPTION_MANY = (
    "error: unknown option '--tet'\n"
    "(Did you mean one of --test, --text?)\n"
)

# No suggestion offered (nothing close enough).
NOTHING = "error: unknown command 'zzzzzz'\n"


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('mytool bulid', COMMAND_ONE),
        ('mytool tet', COMMAND_MANY),
        ('prettier --chekc .', OPTION_ONE),
        ('mytool --tet', OPTION_MANY),
    ])
    def test_matching_unknown_commands_and_options(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('mytool build', ''),
        ('mytool --help', 'Usage: mytool [options] [command]'),
        ('mytool zzzzzz', NOTHING),
        # A cobra tool, which cobra_suggestion owns.
        ('gh reop list', 'unknown command "reop" for "gh"\n\nDid you mean this?\n\trepo\n'),
    ])
    def test_not_matching(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    def test_single_command_suggestion(self):
        assert get_new_command(Command('mytool bulid', COMMAND_ONE)) == [
            'mytool build']

    def test_multiple_command_suggestions(self):
        suggestions = get_new_command(Command('mytool tet', COMMAND_MANY))
        assert 'mytool test' in suggestions
        assert 'mytool text' in suggestions

    def test_single_option_suggestion(self):
        assert get_new_command(Command('prettier --chekc .', OPTION_ONE)) == [
            'prettier --check .']

    def test_multiple_option_suggestions(self):
        suggestions = get_new_command(Command('mytool --tet', OPTION_MANY))
        assert 'mytool --test' in suggestions
        assert 'mytool --text' in suggestions

    def test_flags_and_arguments_are_kept(self):
        assert get_new_command(
            Command('prettier --write --chekc src/index.js', OPTION_ONE)) == [
                'prettier --write --check src/index.js']

    def test_suggestion_is_quoted(self):
        hostile = COMMAND_ONE.replace("build", "build;>PWNED")
        suggestions = get_new_command(Command('mytool bulid', hostile))
        assert "mytool 'build;>PWNED'" in suggestions
        assert 'mytool build;>PWNED' not in suggestions
