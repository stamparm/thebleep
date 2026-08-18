import pytest
from thebleep.rules.man import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('man read', ''),
    Command('man 2 read', ''),
    Command('man 3 read', ''),
    Command('man -s2 read', ''),
    Command('man -s3 read', ''),
    Command('man -s 2 read', ''),
    Command('man -s 3 read', '')])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('man', ''),
    Command('man ', '')])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('man read', ''), ['man 3 read', 'man 2 read', 'read --help']),
    (Command('man missing', "No manual entry for missing\n"), ['missing --help']),
    (Command('man 2 read', ''), 'man 3 read'),
    (Command('man 3 read', ''), 'man 2 read'),
    (Command('man -s2 read', ''), 'man -s3 read'),
    (Command('man -s3 read', ''), 'man -s2 read'),
    (Command('man -s 2 read', ''), 'man -s 3 read'),
    (Command('man -s 3 read', ''), 'man -s 2 read'),
    # A digit in a page name is not a section. `'3' in command.script` was,
    # and turned every one of these into a page nobody has.
    (Command('man python3', ''),
     ['man 3 python3', 'man 2 python3', 'python3 --help']),
    (Command('man ls3', ''), ['man 3 ls3', 'man 2 ls3', 'ls3 --help']),
    (Command('man git-log2', ''),
     ['man 3 git-log2', 'man 2 git-log2', 'git-log2 --help']),
    (Command('man 3 python3', ''), 'man 2 python3')])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command


def test_the_command_is_not_modified_on_the_way_through():
    """`script_parts` used to be inserted into in place.

    It is the command's own cached list, so every rule consulted after this
    one saw a command whose parts had had ' 2 ' spliced into them.

    """
    command = Command('man ls', '')
    get_new_command(command)
    assert command.script_parts == ['man', 'ls']
