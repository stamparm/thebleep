import pytest
from thebleep.rules.missing_space_before_subcommand import (
    match, get_new_command)
from thebleep.types import Command

pytestmark = pytest.mark.usefixtures('no_memoize')


@pytest.fixture(autouse=True)
def all_executables(mocker):
    return mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
        return_value=['git', 'ls', 'npm', 'w', 'watch'])


@pytest.mark.parametrize('script', ['npminstall', 'watchls'])
def test_match(script):
    assert match(Command(script, ''))


@pytest.mark.parametrize('script', ['gitbranch', 'ls-la'])
def test_the_certain_splits_are_the_other_rules(script, mocker):
    """A flag, or a subcommand git itself listed: not a guess, so it is
    answered by `missing_space_before_known_subcommand` in front of the
    spelling correction rather than by this behind it.

    What git lists is stood in for: asked of the real git, this was a test of
    whether a cold Windows runner could start git inside the probe timeout,
    and once it could not.

    """
    from thebleep.rules import missing_space_before_known_subcommand as known

    mocker.patch('thebleep.replay._subcommands',
                 return_value={'branch', 'status', 'push'})
    assert not match(Command(script, ''))
    assert known.match(Command(script, ''))


@pytest.mark.parametrize('script', ['git branch', 'vimfile'])
def test_not_match(script):
    assert not match(Command(script, ''))


@pytest.mark.parametrize('script, result', [
    ('gitbranch', 'git branch'),
    ('ls-la', 'ls -la'),
    ('npminstall webpack', 'npm install webpack'),
    ('watchls', 'watch ls')])
def test_get_new_command(script, result):
    assert get_new_command(Command(script, '')) == result


def test_environment_assignment_is_preserved():
    command = Command('NPM_CONFIG_USER_AGENT=1 npminstall webpack', '')
    assert get_new_command(command) == \
        'NPM_CONFIG_USER_AGENT=1 npm install webpack'


def test_a_shell_builtin_is_a_command_already(mocker):
    """`command`, `time` and `builtin` are not on PATH and are still commands.

    Without this the rule offered to break `command git status` into
    `comm and git status`.

    """
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
        return_value=['comm', 'git', 'ls'])
    assert not match(Command('command git status', ''))
    assert not match(Command('builtin cd /tmp', ''))


class TestWhatItUsedToSplitThatItShouldNot(object):
    """It fires whenever the first word is not runnable but a prefix of it is,
    which on a machine missing one command is nonsense offered confidently."""

    @pytest.fixture(autouse=True)
    def installed(self, mocker):
        """A machine with `su`, `git` and `pip` but no `sudo`, `gitk` or
        `pipx` -- which is every container built from a slim base."""
        return mocker.patch(
            'thebleep.rules.missing_space_before_subcommand'
            '.get_all_executables',
            return_value=['su', 'git', 'pip', 'ls', 'npm', 'watch'])

    def test_sudo_on_a_machine_without_sudo(self):
        """`su do apt-get updte` is not a command either, and `sudo` is a name
        this tool has a model of -- see `wrappers`."""
        assert not match(Command('sudo apt-get updte', 'sudo: not found'))

    def test_a_typo_of_a_wrapper_without_it_installed(self):
        """And one edit out from the same conclusion: `sudoo` is a typo of
        `sudo`, which this tool has a model of whether or not it is
        installed. `su` is a prefix of it, so the split looked available --
        and `su doo id` is not what anybody meant."""
        assert not match(Command('sudoo id', 'bash: sudoo: command not found'))

    @pytest.mark.parametrize('script', ['gitk', 'pipx', 'gitk --all'])
    def test_a_one_character_remainder(self, script):
        """`git k` and `pip x` have never been what anybody meant, and both
        `gitk` and `pipx` are real programs."""
        assert not match(Command(script, 'not found'))

    @pytest.mark.parametrize('script, result', [
        ('npminstall webpack', 'npm install webpack'),
        ('watchls', 'watch ls'),
    ])
    def test_and_what_the_rule_is_actually_for(self, script, result):
        command = Command(script, 'not found')
        assert match(command)
        assert get_new_command(command) == result

    @pytest.mark.parametrize('script', ['gitstatus', 'ls-la'])
    def test_the_certain_ones_belong_to_the_other_rule(self, script):
        """`ls -la` and `git status` are not guesses, so they are answered by
        `missing_space_before_known_subcommand`, which sits in front of the
        spelling correction rather than behind it. Both rules offering the same
        suggestion would put it in the list twice."""
        assert not match(Command(script, 'not found'))
