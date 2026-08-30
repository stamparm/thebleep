import pytest
from thebleep.rules import man
from thebleep.rules.man import match, get_new_command
from thebleep.types import Command


@pytest.fixture(autouse=True)
def installed(mocker):
    """A fixed machine, so `<name> --help` is not offered or withheld by
    accident of whose box the suite runs on -- or of Windows, where `which`
    answers differently again."""
    return mocker.patch.object(
        man, 'which',
        side_effect=lambda name: '/usr/bin/' + name if name in (
            'ls', 'git', 'python3') else None)


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
    # `read` is a shell builtin, so `read --help` is a real place to look.
    (Command('man read', ''), ['man 3 read', 'man 2 read', 'read --help']),
    # `missing` is neither a program nor a builtin, so `missing --help` is not a
    # command and offering it is worse than offering nothing.
    (Command('man missing', "No manual entry for missing\n"), []),
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
    (Command('man ls3', ''), ['man 3 ls3', 'man 2 ls3']),
    (Command('man git-log2', ''),
     ['man 3 git-log2', 'man 2 git-log2']),
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


def test_section_suggestions_preserve_quoted_page():
    command = Command('man "page name"', 'some other output')
    assert get_new_command(command) == [
        'man 3 "page name"', 'man 2 "page name"']
