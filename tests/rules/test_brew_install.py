import pytest
from thebleep.rules.brew_install import match, get_new_command, _get_suggestions
from thebleep.types import Command


@pytest.fixture
def brew_no_available_formula_one():
    return '''Warning: No available formula with the name "giss". Did you mean gist?'''


@pytest.fixture
def brew_no_available_formula_two():
    return '''Warning: No available formula with the name "elasticserar". Did you mean elasticsearch or elasticsearch@6?'''


@pytest.fixture
def brew_no_available_formula_three():
    return '''Warning: No available formula with the name "gitt". Did you mean git, gitg or gist?'''


@pytest.fixture
def brew_install_no_argument():
    return '''Install a formula or cask. Additional options specific to a formula may be'''


@pytest.fixture
def brew_already_installed():
    return '''Warning: git-2.3.5 already installed'''


@pytest.fixture
def brew_no_such_formula_to_uninstall():
    """The same sentence, from `brew uninstall foo`, under `Error:`."""
    return '''Error: No available formula with the name "foo". Did you mean foot, fox, fop or fio?'''


@pytest.mark.parametrize('script', [
    'brew uninstall foo', 'brew reinstall foo'])
def test_not_match_for_a_command_that_is_not_install(
        script, brew_no_such_formula_to_uninstall):
    """`install` is a substring of both, and correcting either to an install
    would undo what was asked for."""
    assert not match(Command(script, brew_no_such_formula_to_uninstall))


def test_suggestions():
    assert _get_suggestions("one") == ['one']
    assert _get_suggestions("one or two") == ['one', 'two']
    assert _get_suggestions("one, two or three") == ['one', 'two', 'three']


def test_match(brew_no_available_formula_one, brew_no_available_formula_two,
               brew_no_available_formula_three, brew_already_installed,
               brew_install_no_argument):
    assert match(Command('brew install giss',
                         brew_no_available_formula_one))
    assert match(Command('brew install elasticserar',
                         brew_no_available_formula_two))
    assert match(Command('brew install gitt',
                         brew_no_available_formula_three))
    assert not match(Command('brew install git',
                             brew_already_installed))
    assert not match(Command('brew install', brew_install_no_argument))


def test_get_new_command(brew_no_available_formula_one, brew_no_available_formula_two,
                         brew_no_available_formula_three):
    assert get_new_command(Command('brew install giss',
                                   brew_no_available_formula_one))\
        == ['brew install gist']
    assert get_new_command(Command('brew install elasticsear',
                                   brew_no_available_formula_two))\
        == ['brew install elasticsearch', 'brew install elasticsearch@6']
    assert get_new_command(Command('brew install gitt',
                                   brew_no_available_formula_three))\
        == ['brew install git', 'brew install gitg', 'brew install gist']

    assert get_new_command(Command('brew install aa',
                                   brew_no_available_formula_one))\
        != 'brew install aha'
