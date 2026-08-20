import pytest
from thebleep.rules.missing_space_before_subcommand import (
    match, get_new_command)
from thebleep.types import Command


@pytest.fixture(autouse=True)
def all_executables(mocker):
    return mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
        return_value=['git', 'ls', 'npm', 'w', 'watch'])


@pytest.mark.parametrize('script', [
    'gitbranch', 'ls-la', 'npminstall', 'watchls'])
def test_match(script):
    assert match(Command(script, ''))


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

    @pytest.mark.parametrize('script', ['gitk', 'pipx', 'gitk --all'])
    def test_a_one_character_remainder(self, script):
        """`git k` and `pip x` have never been what anybody meant, and both
        `gitk` and `pipx` are real programs."""
        assert not match(Command(script, 'not found'))

    @pytest.mark.parametrize('script, result', [
        ('gitstatus', 'git status'),
        ('npminstall webpack', 'npm install webpack'),
        ('ls-la', 'ls -la'),
        ('watchls', 'watch ls'),
    ])
    def test_and_what_the_rule_is_actually_for(self, script, result):
        command = Command(script, 'not found')
        assert match(command)
        assert get_new_command(command) == result
