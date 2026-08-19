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
