# -*- coding: utf-8 -*-

"""`ping` given a URL, which is what pasting from an address bar produces.

The messages are the real ones: iputils on Linux, and what macOS and the BSDs
say instead.

"""

import pytest
from thebleep.rules.ping_url import match, get_new_command
from thebleep.types import Command

LINUX = u'ping: https://github.com/: Name or service not known'
MACOS = u'ping: cannot resolve https://github.com/: Unknown host'
RESOLVER_DOWN = u'ping: github.com: Temporary failure in name resolution'


@pytest.mark.parametrize('script, output', [
    ('ping https://github.com/', LINUX),
    ('ping https://github.com/', MACOS),
    ('ping6 https://github.com/', LINUX),
    ('ping -c 3 https://github.com/', LINUX),
    ('ping http://example.com/some/path', LINUX),
    ('ping github.com/some/path', LINUX),
])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    # A host that simply does not resolve is not this mistake.
    ('ping github.com', RESOLVER_DOWN),
    ('ping nosuchhost', LINUX),
    # It resolved; something else went wrong.
    ('ping https://github.com/', 'ping: socket: Operation not permitted'),
    # Not ping.
    ('curl https://github.com/', LINUX),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, fixed', [
    ('ping https://github.com/', 'ping github.com'),
    ('ping http://example.com/some/path', 'ping example.com'),
    ('ping github.com/some/path', 'ping github.com'),
    ('ping -c 3 https://github.com/', 'ping -c 3 github.com'),
    ('ping6 https://[::1]/', 'ping6 ::1'),
    # A URL can carry a user name, a password and a port, and none of them is
    # the host.
    ('ping https://user:secret@example.com:8443/x', 'ping example.com'),
])
def test_get_new_command(script, fixed):
    assert get_new_command(Command(script, LINUX)) == fixed


def test_a_hostile_host_is_quoted():
    """It comes out of something that was pasted, and goes back to the shell."""
    command = Command('ping https://a;rm.com/x', LINUX)
    assert get_new_command(command) == "ping 'a;rm.com'"


def test_a_quoted_url_is_left_alone():
    """The words come from shlex, so it is not in the script under that
    spelling, and a suggestion identical to the command is not one."""
    command = Command("ping 'https://github.com/'", LINUX)
    assert not match(command)
