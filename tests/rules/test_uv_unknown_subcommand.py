# -*- encoding: utf-8 -*-

import pytest
from thebleep.rules.uv_unknown_subcommand import (
    _get_broken, _get_suggestions, get_new_command, match)
from thebleep.types import Command

# `uv piip install requests` -- single suggestion.
ONE = (
    "error: unrecognized subcommand 'piip'\n"
    "\n"
    "  tip: a similar subcommand exists: 'pip'\n"
    "Usage: uv [OPTIONS] <COMMAND>\n"
    "For more information, try '--help'.\n"
)

# `uv re` -- multiple suggestions.
MANY = (
    "error: unrecognized subcommand 're'\n"
    "\n"
    "  tip: some similar subcommands exist: 'remove', 'tree'\n"
    "Usage: uv [OPTIONS] <COMMAND>\n"
    "For more information, try '--help'.\n"
)

# `uv pip instll requests` -- nested subcommand.
NESTED = (
    "error: unrecognized subcommand 'instll'\n"
    "\n"
    "  tip: a similar subcommand exists: 'install'\n"
    "Usage: uv pip <COMMAND>\n"
    "For more information, try '--help'.\n"
)

# `uv zzzzzz` -- nothing close, no tip offered.
NOTHING = (
    "error: unrecognized subcommand 'zzzzzz'\n"
    "\n"
    "Usage: uv [OPTIONS] <COMMAND>\n"
    "For more information, try '--help'.\n"
)


class TestReadingOutput(object):
    def test_broken_subcommand(self):
        assert _get_broken(ONE) == 'piip'
        assert _get_broken(MANY) == 're'
        assert _get_broken(NESTED) == 'instll'
        assert _get_broken(NOTHING) == 'zzzzzz'

    def test_single_suggestion(self):
        assert _get_suggestions(ONE) == ['pip']

    def test_multiple_suggestions(self):
        assert _get_suggestions(MANY) == ['remove', 'tree']

    def test_nested_suggestion(self):
        assert _get_suggestions(NESTED) == ['install']

    def test_none_offered(self):
        assert _get_suggestions(NOTHING) == []


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('uv piip install requests', ONE),
        ('uv re', MANY),
        ('uv pip instll requests', NESTED),
    ])
    def test_an_unknown_subcommand(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('uv pip install requests', ''),
        ('uv --help', 'An extremely fast Python package manager.'),
        # Somebody else's output.
        ('cargo piip', ONE),
        # When uv has nothing to suggest.
        ('uv zzzzzz', NOTHING),
    ])
    def test_not_matching(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    def test_one_suggestion(self):
        assert get_new_command(
            Command('uv piip install requests', ONE)) == [
                'uv pip install requests']

    def test_multiple_suggestions(self):
        assert get_new_command(Command('uv re', MANY)) == [
            'uv tree', 'uv remove']

    def test_nested_subcommand(self):
        assert get_new_command(
            Command('uv pip instll requests', NESTED)) == [
                'uv pip install requests']

    def test_flags_are_kept(self):
        assert get_new_command(
            Command('uv --directory /tmp piip install requests', ONE)) == [
                'uv --directory /tmp pip install requests']

    def test_a_suggestion_is_quoted(self):
        hostile = ONE.replace("'pip'", "'pip;>PWNED'")
        suggestions = get_new_command(
            Command('uv piip install requests', hostile))
        assert "uv 'pip;>PWNED' install requests" in suggestions
        assert 'uv pip;>PWNED install requests' not in suggestions
