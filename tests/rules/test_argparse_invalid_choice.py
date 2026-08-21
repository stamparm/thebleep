# -*- encoding: utf-8 -*-

"""One rule for every tool built with Python argparse.

Captured from Python 3.14 argparse and pytest 9.0.3.

"""

import pytest
from thebleep.rules.argparse_invalid_choice import match, get_new_command
from thebleep.types import Command

# Subcommand typo in an argparse CLI.
SUBCOMMAND_TYPO = (
    "usage: mytool [-h] {install,build,check} ...\n"
    "mytool: error: argument sub: invalid choice: 'bulid' (choose from install, build, check)\n"
)

# Option choice with space.
PYTEST_COLOR = (
    "ERROR: usage: python.exe -m pytest [options] [file_or_dir] [file_or_dir] [...]\n"
    "python.exe -m pytest: error: argument --color: invalid choice: 'ayt' (choose from yes, no, auto)\n"
)

# Option choice with equals.
OPTION_EQUALS = (
    "usage: mytool [-h] [--format {json,yaml,xml}]\n"
    "mytool: error: argument --format: invalid choice: 'yamll' (choose from json, yaml, xml)\n"
)

# Choices formatted with quotes.
QUOTED_CHOICES = (
    "usage: mytool [-h] {add,commit,status}\n"
    "mytool: error: argument action: invalid choice: 'ad' (choose from 'add', 'commit', 'status')\n"
)


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('mytool bulid', SUBCOMMAND_TYPO),
        ('python -m pytest --color ayt', PYTEST_COLOR),
        ('mytool --format=yamll', OPTION_EQUALS),
        ('mytool ad', QUOTED_CHOICES),
    ])
    def test_matching_invalid_choices(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('mytool build', ''),
        ('pytest --help', 'usage: pytest [options]'),
        # Click tool, which click_suggestion owns.
        ('black --chekc .', "Error: No such option '--chekc'. (Did you mean --check?)\n"),
    ])
    def test_not_matching(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    def test_the_closest_suggestion_comes_first(self):
        suggestions = get_new_command(Command('mytool bulid', SUBCOMMAND_TYPO))
        assert suggestions[0] == 'mytool build'
        assert 'mytool install' in suggestions
        assert 'mytool check' in suggestions

    def test_option_choice_with_space(self):
        suggestions = get_new_command(Command('python -m pytest --color ayt', PYTEST_COLOR))
        assert suggestions[0] == 'python -m pytest --color auto'

    def test_option_choice_with_equals(self):
        suggestions = get_new_command(Command('mytool --format=yamll', OPTION_EQUALS))
        assert suggestions[0] == 'mytool --format=yaml'

    def test_quoted_choices_and_closeness_ordering(self):
        suggestions = get_new_command(Command('mytool ad', QUOTED_CHOICES))
        assert suggestions[0] == 'mytool add'

    def test_suggestion_is_quoted(self):
        hostile = SUBCOMMAND_TYPO.replace("build", "build;>PWNED")
        suggestions = get_new_command(Command('mytool bulid', hostile))
        assert "mytool 'build;>PWNED'" in suggestions
        assert 'mytool build;>PWNED' not in suggestions
