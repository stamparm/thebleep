import pytest
from thebleep.rules.cat_dir import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def isdir(mocker):
    return mocker.patch('thebleep.rules.cat_dir'
                        '.os.path.isdir')


@pytest.mark.parametrize('command', [
    Command('cat foo', 'cat: foo: Is a directory\n'),
    Command('cat /foo/bar/', 'cat: /foo/bar/: Is a directory\n'),
    Command('cat cat/', 'cat: cat/: Is a directory\n'),
])
def test_match(command, isdir):
    isdir.return_value = True
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('cat foo', 'foo bar baz'),
    Command('cat foo bar', 'foo bar baz'),
    Command('notcat foo bar', 'some output'),
])
def test_not_match(command, isdir):
    isdir.return_value = False
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('cat foo', 'cat: foo: Is a directory\n'), 'ls foo'),
    (Command('cat /foo/bar/', 'cat: /foo/bar/: Is a directory\n'), 'ls /foo/bar/'),
    (Command('cat cat', 'cat: cat: Is a directory\n'), 'ls cat'),
])
def test_get_new_command(command, new_command):
    isdir.return_value = True
    assert get_new_command(command) == new_command


def test_environment_assignment_is_preserved(isdir):
    isdir.return_value = True
    command = Command('CAT_MODE=1 cat foo', 'cat: foo: Is a directory\n')
    assert match(command)
    assert get_new_command(command) == 'CAT_MODE=1 ls foo'
