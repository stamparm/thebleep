import pytest
from thebleep.rules.rm_dir import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('rm foo', 'rm: foo: is a directory'),
    Command('rm foo', 'rm: foo: Is a directory'),
    Command('hdfs dfs -rm foo', 'rm: `foo`: Is a directory'),
    Command('./bin/hdfs dfs -rm foo', 'rm: `foo`: Is a directory'),
])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('rm foo', ''),
    Command('hdfs dfs -rm foo', ''),
    Command('./bin/hdfs dfs -rm foo', ''),
    Command('', ''),
    # `'rm' in command.script` matched all of these. The last one it offered to
    # turn into `git rm -rf cached`.
    Command('confirm build', 'build: Is a directory'),
    Command('charm .', '.: Is a directory'),
    Command('/usr/bin/rmdir x', 'x: Is a directory'),
    Command('echo rm', 'rm: Is a directory'),
    Command('git rm cached', 'cached: Is a directory'),
    # `rm` with nothing to remove.
    Command('rm', 'rm: Is a directory'),
])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('rm foo', ''), 'rm -r foo'),
    (Command('sudo rm foo', ''), 'sudo rm -r foo'),
    (Command('hdfs dfs -rm foo', ''), 'hdfs dfs -rm -r foo'),
])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command


def test_the_suggestion_does_not_add_force():
    """`-r` is what makes the removal recursive and is enough to remove a
    directory. `-f` also silences the prompt for a write-protected file, which
    is a confirmation somebody may want."""
    assert '-f' not in get_new_command(Command('rm foo', ''))
