# -*- coding: utf-8 -*-

import pytest
from thebleep.rules import ssh_known_hosts
from thebleep.rules.ssh_known_hosts import match, get_new_command
from thebleep.types import Command

# Verbatim from OpenSSH_9.6p1, `ssh` against a host whose key does not match the
# one in `known_hosts`. The `remove with:` lines are ssh's own.
CHANGED = u"""@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
It is also possible that a host key has just been changed.
The fingerprint for the ED25519 key sent by the remote host is
SHA256:AUJYd8beNJJVaWArMnfg+YafYmSd8FmL9wz1acsGXJA.
Please contact your system administrator.
Add correct host key in /home/u/.ssh/known_hosts to get rid of this message.
Offending ED25519 key in /home/u/.ssh/known_hosts:2
  remove with:
  ssh-keygen -f '/home/u/.ssh/known_hosts' -R '127.0.0.1'
Host key for 127.0.0.1 has changed and you have requested strict checking.
Host key verification failed."""

# OpenSSH 7-era wording: the offending line, and no advice about it.
OLD_CHANGED = u"""@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!
The fingerprint for the RSA key sent by the remote host is
b6:cb:07:34:c0:a0:94:d3:0d:69:83:31:f4:c5:20:9b.
Add correct host key in /home/u/.ssh/known_hosts to get rid of this message.
Offending RSA key in /home/u/.ssh/known_hosts:3
RSA host key for 98.765.432.321 has changed and you have requested strict checking.
Host key verification failed."""

# The other warning: the key for the name and the key for the address disagree.
# Two entries are named, and only one of them is the offending one.
SPOOFING = u"""@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@       WARNING: POSSIBLE DNS SPOOFING DETECTED!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
The ED25519 host key for example.com has changed,
and the key for the corresponding IP address 10.0.0.1
is unknown. This could either mean that
DNS SPOOFING is happening or the IP address for the host
and its host key have changed at the same time.
Offending key for IP in /home/u/.ssh/known_hosts:1
Matching host key in /home/u/.ssh/known_hosts:2
Warning: the ED25519 host key for 'example.com' differs from the key for the IP address '10.0.0.1'
Are you sure you want to continue connecting (yes/no)?"""


@pytest.mark.parametrize('output', [CHANGED, OLD_CHANGED, SPOOFING])
def test_match(output):
    assert match(Command('ssh user@host', output))
    assert match(Command('scp a user@host:b', output))
    assert not match(Command('notssh user@host', output))
    assert not match(Command('ssh user@host', ''))


def test_no_match_without_somewhere_to_remove_from():
    """A warning we cannot act on precisely is one to stay out of."""
    assert not match(Command('ssh user@host', '\n'.join(
        line for line in CHANGED.split('\n') if 'Offending' not in line)))


def test_the_removal_is_part_of_the_command():
    """Not a side effect: what the user approves is what runs."""
    assert not hasattr(ssh_known_hosts, 'side_effect')
    assert get_new_command(Command('ssh user@host', CHANGED)) == (
        "ssh-keygen -f /home/u/.ssh/known_hosts -R 127.0.0.1"
        " && ssh user@host")


def test_the_host_comes_from_ssh_not_from_the_command_line():
    """`ssh prod` may be an alias in ~/.ssh/config for something else, and it is
    the something else that is in known_hosts."""
    assert '127.0.0.1' in get_new_command(Command('ssh prod', CHANGED))


def test_older_ssh_that_does_not_say_what_to_run():
    assert get_new_command(Command('ssh user@host', OLD_CHANGED)) == (
        "ssh-keygen -f /home/u/.ssh/known_hosts -R 98.765.432.321"
        " && ssh user@host")


def test_only_the_offending_entry_is_dropped():
    """The spoofing warning names the matching entry too, and that one is right.

    The old side effect matched `Matching host key in <file>:<line>` as well and
    deleted it, taking out the entry that was correct.

    """
    new = get_new_command(Command('ssh example.com', SPOOFING))
    assert new == ("ssh-keygen -f /home/u/.ssh/known_hosts -R 10.0.0.1"
                   " && ssh example.com")
    assert 'example.com -R' not in new


def test_a_hostile_known_hosts_path_is_quoted(set_shell):
    from thebleep.shells import Bash

    set_shell(Bash)
    output = CHANGED.replace('/home/u/.ssh/known_hosts',
                             '/home/u/$(touch pwned)/known_hosts')
    assert "'/home/u/$(touch pwned)/known_hosts'" in \
        get_new_command(Command('ssh user@host', output))
