import pytest
from thebleep.rules.whois import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('whois https://en.wikipedia.org/wiki/Main_Page', ''),
    Command('whois https://en.wikipedia.org/', ''),
    Command('whois meta.unix.stackexchange.com', '')])
def test_match(command):
    assert match(command)


def test_not_match():
    assert not match(Command('whois', ''))


# `whois com` actually makes sense
@pytest.mark.parametrize('command, new_command', [
    (Command('whois https://en.wikipedia.org/wiki/Main_Page', ''),
     'whois en.wikipedia.org'),
    (Command('whois https://en.wikipedia.org/', ''),
     'whois en.wikipedia.org'),
    (Command('whois meta.unix.stackexchange.com', ''),
     ['whois unix.stackexchange.com',
      'whois stackexchange.com',
      'whois com'])])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command


@pytest.mark.parametrize('script', [
    'whois localhost',
    'whois myserver',
    'whois -h',
])
def test_not_match_without_anything_to_shorten(script):
    """It used to match anything at all and then hand back `None`, which is
    what the user was shown."""
    assert not match(Command(script, ''))


def test_a_host_with_a_space_in_it_is_quoted(set_shell):
    from thebleep.shells import Bash

    set_shell(Bash)
    assert get_new_command(Command("whois 'a.b c.example.com'", '')) == [
        "whois 'b c.example.com'", 'whois example.com', 'whois com']


def test_environment_assignment_is_preserved():
    command = Command('WHOIS_TIMEOUT=5 whois meta.unix.stackexchange.com', '')
    assert get_new_command(command) == [
        'WHOIS_TIMEOUT=5 whois unix.stackexchange.com',
        'WHOIS_TIMEOUT=5 whois stackexchange.com',
        'WHOIS_TIMEOUT=5 whois com']
