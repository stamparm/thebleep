import pytest
from thebleep.rules.misplaced_space import match, get_new_command
from thebleep.types import Command


@pytest.fixture(autouse=True)
def executables(mocker):
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
        return_value=['sudo', 'su', 'git', 'go'])


@pytest.fixture(autouse=True)
def builtins(mocker):
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.shell'
        '.get_builtin_commands', return_value=[])


@pytest.mark.usefixtures('no_memoize')
def test_match(mocker):
    mocker.patch('thebleep.rules.misplaced_space.which', return_value=None)

    assert match(Command('sud osu', "Command 'sud' not found"))


@pytest.mark.usefixtures('no_memoize')
def test_get_new_command(mocker):
    mocker.patch('thebleep.rules.misplaced_space.which', return_value=None)

    assert get_new_command(Command('sud osu', '')) == ['sudo su']


@pytest.mark.usefixtures('no_memoize')
def test_not_match_when_no_clean_split(mocker):
    mocker.patch('thebleep.rules.misplaced_space.which', return_value=None)

    assert not match(Command('gti commit', "gti: command not found"))


@pytest.mark.usefixtures('no_memoize')
def test_not_match_when_first_word_runs(mocker):
    mocker.patch('thebleep.rules.misplaced_space.which',
                 return_value='/usr/bin/sudo')

    assert not match(Command('sud osu', ''))
