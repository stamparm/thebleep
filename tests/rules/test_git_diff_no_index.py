import pytest
from thebleep.rules.git_diff_no_index import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('git diff foo bar', '')])
def test_match(command):
    assert match(command)


def test_a_diff_argument_is_not_the_subcommand():
    assert not match(Command('git show diff foo', ''))


def test_global_options_do_not_change_the_subcommand():
    command = Command('git -C worktree diff foo bar', '')
    assert match(command)
    assert get_new_command(command) == \
        'git -C worktree diff --no-index foo bar'


@pytest.mark.parametrize('command', [
    Command('git diff --no-index foo bar', ''),
    Command('git diff foo', ''),
    Command('git diff foo bar baz', '')])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('git diff foo bar', ''), 'git diff --no-index foo bar')])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command
