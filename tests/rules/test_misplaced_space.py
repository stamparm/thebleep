import pytest
from thebleep.rules.misplaced_space import match, get_new_command
from thebleep.types import Command


@pytest.fixture(autouse=True)
def executables(mocker):
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
        return_value=['sudo', 'su', 'git', 'go'])


@pytest.fixture(autouse=True)
def subcommands(mocker):
    """git documents a few subcommands; nothing else documents any."""
    known = {'git': ['log', 'status', 'commit']}
    return mocker.patch('thebleep.vocabulary.subcommands',
                        side_effect=lambda tool, prefix=(): list(
                            known.get(tool, [])))


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


@pytest.mark.usefixtures('no_memoize')
def test_not_match_when_second_word_is_too_short(mocker):
    """A one-letter argument is not evidence of a second command.

    The executable set is deliberately the smallest one that made the old
    implementation false-positive: both `rm` and `mf` are runnable, so
    `rmm f` would otherwise be split into `rm mf`.
    """
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
        return_value=['rm', 'mf'])
    mocker.patch(
        'thebleep.rules.misplaced_space.which', return_value=None)

    assert not match(Command('rmm f', "Command 'rmm' not found"))


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, fixed', [
    ('gi tlog', 'git log'),
    ('gi tstatus -s', 'git status -s'),
])
def test_the_second_half_may_be_a_subcommand(mocker, script, fixed):
    """`gi tlog` used to be `git tlog`: `log` is no program, so the split
    was not seen and `no_command` fixed the first word alone."""
    mocker.patch('thebleep.rules.misplaced_space.which', return_value=None)

    assert match(Command(script, ''))
    assert get_new_command(Command(script, '')) == [fixed]


@pytest.mark.usefixtures('no_memoize')
def test_an_undocumented_second_half_is_no_split(mocker):
    mocker.patch('thebleep.rules.misplaced_space.which', return_value=None)

    assert not match(Command('gi tfoo', ''))
