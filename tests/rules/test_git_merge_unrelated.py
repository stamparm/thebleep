import pytest
from thebleep.rules.git_merge_unrelated import match, get_new_command
from thebleep.types import Command


output = 'fatal: refusing to merge unrelated histories'


def test_match():
    assert match(Command('git merge test', output))
    assert not match(Command('git merge master', ''))
    assert not match(Command('ls', output))


@pytest.mark.parametrize('command, new_command', [
    (Command('git merge local', output),
     'git merge --allow-unrelated-histories local'),
    (Command('git merge -m "test" local', output),
     'git merge --allow-unrelated-histories -m "test" local'),
    (Command('git merge -m "test local" local', output),
     'git merge --allow-unrelated-histories -m "test local" local'),
    (Command('git merge local && echo done', output),
     'git merge --allow-unrelated-histories local && echo done')])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command


def test_not_match_when_merge_is_configuration_data():
    assert not match(Command('git config merge.tool vim', output))


def test_not_match_when_flag_is_already_present():
    command = Command('git merge --allow-unrelated-histories local', output)

    assert not match(command)
