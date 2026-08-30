import pytest
from thebleep.rules.apt_get_search import get_new_command, match
from thebleep.types import Command


def test_match():
    assert match(Command('apt-get search foo', ''))


@pytest.mark.parametrize('command', [
    Command('apt-cache search foo', ''),
    Command('aptitude search foo', ''),
    Command('apt search foo', ''),
    Command('apt-get install foo', ''),
    Command('apt-get source foo', ''),
    Command('apt-get clean', ''),
    Command('apt-get remove', ''),
    Command('apt-get update', '')
])
def test_not_match(command):
    assert not match(command)


def test_get_new_command():
    new_command = get_new_command(Command('apt-get search foo', ''))
    assert new_command == 'apt-cache search foo'


def test_prefixed_command_keeps_assignment():
    command = Command('APT_CONFIG=/tmp/config apt-get search foo', '')
    assert match(command)
    assert get_new_command(command) == \
        'APT_CONFIG=/tmp/config apt-cache search foo'
