import pytest
from thebleep.rules.git_remote_seturl_add import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('git remote set-url origin url', "fatal: No such remote")])
def test_match(command):
    assert match(command)


def test_set_url_text_in_another_command_is_not_a_remote_operation():
    assert not match(Command('git show set-url', "fatal: No such remote"))


@pytest.mark.parametrize('command', [
    Command('git remote set-url origin url', ""),
    Command('git remote add origin url', ''),
    Command('git remote remove origin', ''),
    Command('git remote prune origin', ''),
    Command('git remote set-branches origin branch', '')])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('git remote set-url origin git@github.com:stamparm/thebleep.git', ''),
     'git remote add origin git@github.com:stamparm/thebleep.git')])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command
