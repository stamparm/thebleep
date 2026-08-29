import pytest
from thebleep.rules.git_pull_uncommitted_changes import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def output():
    return '''error: Cannot pull with rebase: You have unstaged changes.'''


def test_match(output):
    assert match(Command('git pull', output))
    assert not match(Command('git pull', ''))
    assert not match(Command('ls', output))


def test_a_configuration_token_is_not_a_pull(output):
    assert not match(Command('git config --get-regexp pull', output))


def test_get_new_command(output):
    assert (get_new_command(Command('git pull', output))
            == "git stash && git pull && git stash pop")
