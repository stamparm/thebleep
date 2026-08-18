"""Correcting an ssh host key warning, without hiding it.

A changed host key can mean a rebuilt server or a recycled address. It can also
mean somebody is between you and the machine, which is why ssh shouts about it.
So this offers the removal as a command, in front of the ssh call, naming the
file and the host it will drop the key for. Whoever reads it can decide.

What it used to do was return the ssh command unchanged and delete the offending
line from `known_hosts` in a side effect. All the user saw was their own command
again, and accepting it made a man-in-the-middle warning go away with no trace
of why.

"""

import re
from thebleep.shells import shell
from thebleep.utils import for_app

commands = ('ssh', 'scp')

WARNINGS = (
    'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!',
    'WARNING: POSSIBLE DNS SPOOFING DETECTED!',
)

# Which file, and which line in it, ssh objects to. Deliberately not
# `Matching host key`, which the old side effect also matched and deleted: on
# the DNS spoofing warning that line is the entry that is *correct*.
OFFENDING = re.compile(r'Offending (?:key for IP|\S+ key) in (.+):(\d+)')

# Current ssh prints the command to run, already quoted:
#
#   Offending ED25519 key in /home/u/.ssh/known_hosts:2
#     remove with:
#     ssh-keygen -f '/home/u/.ssh/known_hosts' -R '10.0.0.1'
#
# The host is read out of it rather than guessed from the command line, where it
# may be an alias out of `~/.ssh/config` and not what is in `known_hosts` at all.
REMOVE_WITH = re.compile(r"ssh-keygen -f '[^']*' -R '([^']*)'")

# On the DNS spoofing warning the offending entry is the one for the IP address.
DIFFERS = re.compile(r"Warning: the \S+ host key for '([^']+)' differs from "
                     r"the key for the IP address '([^']+)'")

# Older ssh says what changed without saying what to do about it.
HOST_CHANGED = re.compile(r'host key for (\S+) has changed', re.IGNORECASE)


def _removal(output):
    """The `ssh-keygen -R` that drops the entry ssh objects to, or None."""
    offending = OFFENDING.search(output)
    if not offending:
        return None

    for pattern, group in ((REMOVE_WITH, 1), (DIFFERS, 2), (HOST_CHANGED, 1)):
        found = pattern.search(output)
        if found:
            return u'ssh-keygen -f {} -R {}'.format(
                shell.quote(offending.group(1)),
                shell.quote(found.group(group)))

    return None


@for_app(*commands)
def match(command):
    # No `startswith` check: `for_app` has already established which command
    # this is, and does it without being fooled by `TERM=xterm-256color ssh`.
    return (any(warning in command.output for warning in WARNINGS)
            and _removal(command.output) is not None)


def get_new_command(command):
    return shell.and_(_removal(command.output), command.script)
