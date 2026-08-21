# -*- encoding: utf-8 -*-

"""One rule for every tool built with Python's argparse.

Every fixture here was printed by a real program. The three shapes below were
captured from argparse on Python 3.9, 3.11, 3.12, 3.13 and 3.14 -- the wording is
identical on all of them -- and `PYTEST_COLOR` from pytest 9.1.1.

The rule arrived with fixtures that showed the choices *unquoted* (`choose from
yes, no, auto`), which argparse has never printed in any version this project
supports. The rule worked anyway, because it strips quotes -- but tests against
output no tool produces are how four rules in this package came to be dead
while their tests passed, so they are captured here instead.

"""

import pytest
from thebleep.rules.argparse_invalid_choice import match, get_new_command
from thebleep.types import Command

# A mistyped subcommand.
SUBCOMMAND_TYPO = (
    'usage: mytool [-h] [--format {json,yaml,xml}] [--color {yes,no,auto}]\n'
    '              {install,build,check} ...\n'
    "mytool: error: argument sub: invalid choice: 'bulid'"
    " (choose from 'install', 'build', 'check')\n"
)

# A choice glued to its option with an `=`.
OPTION_EQUALS = (
    'usage: mytool [-h] [--format {json,yaml,xml}]\n'
    "mytool: error: argument --format: invalid choice: 'yamll'"
    " (choose from 'json', 'yaml', 'xml')\n"
)

# An option with a short alias, which argparse names as `--color/-c`. The rule
# was not tested against this and it is what half the options in the world look
# like.
OPTION_WITH_ALIAS = (
    'usage: mytool [-h] [--color {yes,no,auto}]\n'
    "mytool: error: argument --color/-c: invalid choice: 'ayt'"
    " (choose from 'yes', 'no', 'auto')\n"
)

# pytest 9.1.1, which is argparse underneath.
PYTEST_COLOR = (
    'ERROR: usage: python -m pytest [options] [file_or_dir]'
    ' [file_or_dir] [...]\n'
    "python -m pytest: error: argument --color: invalid choice: 'ayt'"
    " (choose from 'yes', 'no', 'auto')\n"
)


class TestMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('mytool bulid', SUBCOMMAND_TYPO),
        ('mytool --format=yamll', OPTION_EQUALS),
        ('mytool --color ayt', OPTION_WITH_ALIAS),
        ('python -m pytest --color=ayt', PYTEST_COLOR),
    ])
    def test_matching_invalid_choices(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output', [
        ('mytool build', ''),
        ('pytest --help', 'usage: pytest [options]'),
        # A Click tool, which `click_suggestion` owns.
        ('black --chekc .',
         "Error: No such option '--chekc'. (Did you mean --check?)\n"),
        # A gnulib tool, which `invalid_argument_for_option` owns: the same
        # idea, a different wording, and the choices on their own lines.
        ('ls --sort=nmae',
         "ls: invalid argument 'nmae' for '--sort'\n"
         "Valid arguments are:\n  - 'none'\n  - 'time'\n"),
    ])
    def test_not_matching(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    def test_the_closest_suggestion_comes_first(self):
        suggestions = get_new_command(Command('mytool bulid', SUBCOMMAND_TYPO))
        assert suggestions[0] == 'mytool build'
        assert 'mytool install' in suggestions
        assert 'mytool check' in suggestions

    def test_a_choice_glued_to_its_option(self):
        suggestions = get_new_command(
            Command('mytool --format=yamll', OPTION_EQUALS))
        assert suggestions[0] == 'mytool --format=yaml'

    def test_a_choice_as_its_own_word(self):
        suggestions = get_new_command(
            Command('mytool --color ayt', OPTION_WITH_ALIAS))
        assert suggestions[0] == 'mytool --color auto'

    def test_pytest(self):
        suggestions = get_new_command(
            Command('python -m pytest --color=ayt', PYTEST_COLOR))
        assert suggestions[0] == 'python -m pytest --color=auto'

    def test_the_rest_of_the_command_survives(self):
        assert get_new_command(
            Command('python -m pytest -x --color=ayt tests/',
                    PYTEST_COLOR))[0] \
            == 'python -m pytest -x --color=auto tests/'

    def test_suggestion_is_quoted(self):
        """A choice comes out of the tool's output, and the result is `eval`led.

        argparse gets its choices from the program's own source, so this is the
        least reachable of the injection paths -- and quoting a plain word costs
        nothing, which is why every rule that reads a name does it.

        """
        hostile = SUBCOMMAND_TYPO.replace("'build'", "'build;>PWNED'")
        suggestions = get_new_command(Command('mytool bulid', hostile))
        assert "mytool 'build;>PWNED'" in suggestions
        assert 'mytool build;>PWNED' not in suggestions
