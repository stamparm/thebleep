import pytest
from thebleep.rules.git_remote_delete import get_new_command, match
from thebleep.types import Command


def test_match():
    assert match(Command('git remote delete foo', ''))


@pytest.mark.parametrize('command', [
    Command('git remote remove foo', ''),
    Command('git remote add foo', ''),
    Command('git commit', '')
])
def test_not_match(command):
    assert not match(command)


def test_not_match_when_remote_delete_is_configuration_data():
    assert not match(Command('git config remote.delete "remote delete"', ''))


@pytest.mark.parametrize('command, new_command', [
    (Command('git remote delete foo', ''), 'git remote remove foo'),
    (Command('git remote delete delete', ''), 'git remote remove delete'),
])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command


def test_get_new_command_preserves_text_in_a_remote_name():
    command = Command('DELETE=delete git remote delete foo', '')

    assert get_new_command(command) == 'DELETE=delete git remote remove foo'
