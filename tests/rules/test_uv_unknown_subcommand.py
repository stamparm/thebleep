# -*- encoding: utf-8 -*-

"""Every fixture here was printed by a real uv 0.12.5.

The hand-written ones this replaces were close but not right, and wrong in the
direction that matters: `uv pip instll` was given a single suggestion, where uv
really offers three, so the test agreed with an ordering that had never been
exercised.

"""

import pytest
from thebleep.rules.uv_unknown_subcommand import (
    _get_broken, _get_suggestions, get_new_command, match)
from thebleep.types import Command

# `uv piip install requests` -- one suggestion, so the wording is singular.
ONE = (
    "error: unrecognized subcommand 'piip'\n"
    "\n"
    "  tip: a similar subcommand exists: 'pip'\n"
    "\n"
    "Usage: uv [OPTIONS] <COMMAND>\n"
    "\n"
    "For more information, try '--help'.\n"
)

# `uv re` -- two, and neither of them is what the closest one turns out to be.
MANY = (
    "error: unrecognized subcommand 're'\n"
    "\n"
    "  tip: some similar subcommands exist: 'remove', 'tree'\n"
    "\n"
    "Usage: uv [OPTIONS] <COMMAND>\n"
    "\n"
    "For more information, try '--help'.\n"
)

# `uv ad requests` -- uv offers `audit` before `add`.
ORDER = (
    "error: unrecognized subcommand 'ad'\n"
    "\n"
    "  tip: some similar subcommands exist: 'audit', 'add'\n"
    "\n"
    "Usage: uv [OPTIONS] <COMMAND>\n"
    "\n"
    "For more information, try '--help'.\n"
)

# `uv pip instll requests` -- a subcommand of a subcommand. Note the usage
# line names `uv pip`, and that there are three suggestions rather than the
# one `instll` obviously meant.
NESTED = (
    "error: unrecognized subcommand 'instll'\n"
    "\n"
    "  tip: some similar subcommands exist: 'list', 'uninstall', 'install'\n"
    "\n"
    "Usage: uv pip [OPTIONS] <COMMAND>\n"
    "\n"
    "For more information, try '--help'.\n"
)

# `uv tool runn ruff` -- another namespace, and the singular wording again.
TOOL = (
    "error: unrecognized subcommand 'runn'\n"
    "\n"
    "  tip: a similar subcommand exists: 'run'\n"
    "\n"
    "Usage: uv tool [OPTIONS] <COMMAND>\n"
    "\n"
    "For more information, try '--help'.\n"
)

# `uv python instal 3.12` -- the third namespace, with an argument after the
# subcommand that has to survive.
PYTHON = (
    "error: unrecognized subcommand 'instal'\n"
    "\n"
    "  tip: some similar subcommands exist: 'list', 'uninstall', 'install'\n"
    "\n"
    "Usage: uv python [OPTIONS] <COMMAND>\n"
    "\n"
    "For more information, try '--help'.\n"
)

# `uv zzzzzz` -- nothing was close, so uv prints no tip.
NOTHING = (
    "error: unrecognized subcommand 'zzzzzz'\n"
    "\n"
    "Usage: uv [OPTIONS] <COMMAND>\n"
    "\n"
    "For more information, try '--help'.\n"
)


class TestReadingOutput(object):
    @pytest.mark.parametrize('output, broken', [
        (ONE, 'piip'),
        (MANY, 're'),
        (ORDER, 'ad'),
        (NESTED, 'instll'),
        (TOOL, 'runn'),
        (PYTHON, 'instal'),
        (NOTHING, 'zzzzzz'),
    ])
    def test_the_subcommand_uv_choked_on(self, output, broken):
        assert _get_broken(output) == broken

    @pytest.mark.parametrize('output, suggestions', [
        (ONE, ['pip']),
        (MANY, ['remove', 'tree']),
        (ORDER, ['audit', 'add']),
        (NESTED, ['list', 'uninstall', 'install']),
        (TOOL, ['run']),
        (PYTHON, ['list', 'uninstall', 'install']),
        # No tip line, so nothing to read.
        (NOTHING, []),
    ])
    def test_what_uv_offered(self, output, suggestions):
        """In uv's own order; `get_new_command` is what reorders them."""
        assert _get_suggestions(output) == suggestions

    def test_the_usage_line_is_not_mistaken_for_a_tip(self):
        """It is the only other line with quotes on it."""
        assert _get_suggestions(NOTHING) == []


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('uv piip install requests', ONE),
        ('uv re', MANY),
        ('uv ad requests', ORDER),
        ('uv pip instll requests', NESTED),
        ('uv tool runn ruff', TOOL),
        ('uv python instal 3.12', PYTHON),
    ])
    def test_an_unknown_subcommand(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('uv pip install requests', ''),
        ('uv --help', 'An extremely fast Python package manager.'),
        # Somebody else's output.
        ('cargo piip', ONE),
        # `uv` on its own has no subcommand to correct.
        ('uv', ONE),
        # Nothing was close enough for uv to name, so there is nothing to
        # offer -- guessing at that point is worse than saying nothing.
        ('uv zzzzzz', NOTHING),
    ])
    def test_not_matching(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    def test_one_suggestion(self):
        assert get_new_command(
            Command('uv piip install requests', ONE)) == [
                'uv pip install requests']

    def test_the_closest_is_offered_first(self):
        """Not uv's order: `tree` contains `re`, `remove` merely starts with
        it."""
        assert get_new_command(Command('uv re', MANY)) == [
            'uv tree', 'uv remove']

    def test_uvs_order_is_not_kept_when_it_is_the_wrong_way_round(self):
        """uv names `audit` first for `ad`, and `add` is what was meant."""
        assert get_new_command(Command('uv ad requests', ORDER)) == [
            'uv add requests', 'uv audit requests']

    def test_a_subcommand_of_a_subcommand(self):
        assert get_new_command(
            Command('uv pip instll requests', NESTED)) == [
                'uv pip install requests',
                'uv pip uninstall requests',
                'uv pip list requests']

    @pytest.mark.parametrize('script, output, first', [
        ('uv tool runn ruff', TOOL, 'uv tool run ruff'),
        ('uv python instal 3.12', PYTHON, 'uv python install 3.12'),
    ])
    def test_the_other_namespaces(self, script, output, first):
        assert get_new_command(Command(script, output))[0] == first

    def test_flags_are_kept(self):
        assert get_new_command(
            Command('uv --directory /tmp piip install requests', ONE)) == [
                'uv --directory /tmp pip install requests']

    def test_a_suggestion_is_quoted(self):
        """uv's subcommands are its own, but this reads a name out of output
        and the result goes back to the shell, so it is quoted like every
        other rule that does that. See `tests/test_injection.py`."""
        hostile = ONE.replace("'pip'", "'pip;>PWNED'")
        suggestions = get_new_command(
            Command('uv piip install requests', hostile))
        assert "uv 'pip;>PWNED' install requests" in suggestions
        assert 'uv pip;>PWNED install requests' not in suggestions
