from thebleep.rules.man_no_space import match, get_new_command
from thebleep.types import Command


def test_match():
    assert match(Command('mandiff', 'mandiff: command not found'))
    assert not match(Command('', ''))


def test_get_new_command():
    assert get_new_command(Command('mandiff', '')) == 'man diff'


def test_prefixed_command_keeps_assignment():
    command = Command('MANWIDTH=80 mandiff', 'mandiff: command not found')
    assert match(command)
    assert get_new_command(command) == 'MANWIDTH=80 man diff'
