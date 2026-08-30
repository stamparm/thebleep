import pytest
from thebleep.rules.unsudo import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('output', [
    'you cannot perform this operation as root'])
def test_match(output):
    assert match(Command('sudo ls', output))


def test_not_match():
    assert not match(Command('', ''))
    assert not match(Command('sudo ls', 'Permission denied'))
    assert not match(Command('ls', 'you cannot perform this operation as root'))
    assert not match(Command('', 'you cannot perform this operation as root'))
    assert not match(Command('sudo -E ls',
                             'you cannot perform this operation as root'))
    assert not match(Command('sudo -u root ls',
                             'you cannot perform this operation as root'))


@pytest.mark.parametrize('before, after', [
    ('sudo ls', 'ls'),
    ('sudo pacaur -S helloworld', 'pacaur -S helloworld')])
def test_get_new_command(before, after):
    assert get_new_command(Command(before, '')) == after


@pytest.mark.parametrize('script', ['sudo -E ls', 'sudo'])
def test_get_new_command_does_not_strip_an_option_or_bare_sudo(script):
    assert get_new_command(Command(
        script, 'you cannot perform this operation as root')) == script
