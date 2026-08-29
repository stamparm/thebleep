# -*- coding: utf-8 -*-

"""Finding the command behind the words in front of it.

The point of these is as much what is *not* unwrapped as what is: an unwrapping
that goes one word too far mistakes an option's value for the command, and then
every rule is asked about the wrong thing.

"""

import pytest
from thebleep import wrappers
from thebleep.shells import Generic

shell = Generic()


def peel(script):
    return wrappers.peel(script, shell.split_command(script))


@pytest.mark.parametrize('script, prefix, command', [
    # The plain forms.
    ('sudo git chekout master', 'sudo ', 'git chekout master'),
    ('doas apt instal vim', 'doas ', 'apt instal vim'),
    ('nohup ./deploy.sh', 'nohup ', './deploy.sh'),
    ('command git chekout', 'command ', 'git chekout'),
    ('builtin cd /tmp', 'builtin ', 'cd /tmp'),
    # Options with values, separate and glued on.
    ('sudo -u www-data git chekout', 'sudo -u www-data ', 'git chekout'),
    ('sudo -uwww-data git chekout', 'sudo -uwww-data ', 'git chekout'),
    ('sudo --user www-data git chekout', 'sudo --user www-data ',
     'git chekout'),
    ('sudo --user=www-data git chekout', 'sudo --user=www-data ',
     'git chekout'),
    ('nice -n 10 cargo buld', 'nice -n 10 ', 'cargo buld'),
    ('nice --adjustment=10 cargo buld', 'nice --adjustment=10 ', 'cargo buld'),
    ('stdbuf -oL grep x file', 'stdbuf -oL ', 'grep x file'),
    ('stdbuf -o L grep x file', 'stdbuf -o L ', 'grep x file'),
    # `nice -10` is the old spelling of `nice -n 10`.
    ('nice -10 cargo buld', 'nice -10 ', 'cargo buld'),
    # Clustered booleans.
    ('sudo -EH npm sart', 'sudo -EH ', 'npm sart'),
    ('sudo -E -H npm sart', 'sudo -E -H ', 'npm sart'),
    ('setsid -fw nohup git chekout', 'setsid -fw nohup ', 'git chekout'),
    # Assignments, which both sudo and env take.
    ('env FOO=bar npm sart', 'env FOO=bar ', 'npm sart'),
    ('env FOO=bar BAZ=qux npm sart', 'env FOO=bar BAZ=qux ', 'npm sart'),
    ('sudo FOO=bar npm sart', 'sudo FOO=bar ', 'npm sart'),
    ('env -i -u HOME cargo buld', 'env -i -u HOME ', 'cargo buld'),
    # `--` ends the options.
    ('sudo -- git chekout', 'sudo -- ', 'git chekout'),
    # And they nest.
    ('setsid -f nohup nice -n 5 sudo -u root git chekout x',
     'setsid -f nohup nice -n 5 sudo -u root ', 'git chekout x'),
    # Whatever whitespace was between them is kept, in the prefix.
    ('sudo   git chekout', 'sudo   ', 'git chekout'),
])
def test_what_is_peeled(script, prefix, command):
    assert peel(script) == (prefix, command)
    # The two halves are the script, so putting them back cannot change it.
    assert prefix + command == script


@pytest.mark.parametrize('script', [
    # Nothing in front of it.
    'git chekout master',
    'ls',
    # A wrapper that runs a shell, an editor, or nothing at all.
    'sudo -i',
    'sudo -i git status',
    'sudo -s git status',
    'sudo -e /etc/hosts',
    'sudo -l git',
    'sudo -V',
    'sudo --login git status',
    'doas -s git status',
    'command -v git',
    'command -V git',
    # `time` prints a report of its own into the output the rules read.
    'time git chekout',
    # `env -S` re-splits its argument into a command line of its own.
    'env -S "git status"',
    'env --split-string="git status"',
    # An option nobody here has heard of: it may take a value, and then the
    # value is not the command.
    'sudo --wibble git status',
    'nice --unknown 10 cargo build',
    # The wrapper with nothing after it.
    'sudo',
    'env',
    'nice -n 10',
    'sudo -u www-data',
    # More than one command, so the first word is not the whole story.
    'echo x | sudo tee /etc/hosts',
    'sudo git status; rm -rf /tmp/x',
    'sudo git status && echo done',
    'sudo git status > out.txt',
    'sudo `id` git status',
    # A wrapper word that would have to be re-quoted to be handed back.
    "sudo -u 'my user' git status",
    'env "FOO=a b" npm start',
])
def test_what_is_left_alone(script):
    assert peel(script) == (None, None)


def test_the_command_keeps_its_own_quoting():
    """The words came out of shlex; the command must not be rebuilt from them."""
    script = 'sudo git commit -m "a message with spaces"'
    prefix, command = peel(script)
    assert prefix == 'sudo '
    assert command == 'git commit -m "a message with spaces"'


def test_a_wrapper_named_by_path_is_not_one():
    """`/usr/bin/sudo` is the same program, and this is a name comparison."""
    assert peel('/usr/bin/sudo git status') == (None, None)


@pytest.mark.parametrize('script, app', [
    ('sudo git chekout', 'git'),
    ('nice -n 10 cargo buld', 'cargo'),
    ('env FOO=bar npm sart', 'npm'),
    ('setsid -f sudo -u root git chekout', 'git'),
    # Dispatch is allowed to look past syntax that stops `peel`: loading the
    # git rules for something git-shaped costs a millisecond and cannot be
    # wrong, where cutting the script in two could be.
    ('sudo git status; rm -rf /tmp/x', 'git'),
    ('git chekout', None),
    ('sudo -i', None),
    ('sudo', None),
])
def test_which_app_dispatch_is_told_about(script, app):
    assert wrappers.wrapped_app(shell.split_command(script)) == app


@pytest.mark.parametrize('parts, index', [
    (['git', 'chekout'], 0),
    (['sudo', 'git', 'chekout'], 1),
    (['env', 'FOO=bar', 'npm', 'sart'], 2),
    (['sudo', '-u', 'root', 'git', 'chekout'], 3),
    (['sudo', '-i'], None),
])
def test_wrapped_command_index(parts, index):
    assert wrappers.wrapped_command_index(parts) == index


class TestDispatch(object):
    def test_both_names_reach_dispatch(self):
        """A rule may be about the wrapper or about what it wraps."""
        from thebleep import rulepack
        from thebleep.types import Command

        assert rulepack.command_apps(Command('sudo git chekout', '')) == \
            frozenset({'sudo', 'git'})

    def test_an_unwrapped_command_is_just_itself(self):
        from thebleep import rulepack
        from thebleep.types import Command

        assert rulepack.command_apps(Command('git chekout', '')) == \
            frozenset({'git'})

    def test_assignments_in_front_are_still_skipped(self):
        from thebleep import rulepack
        from thebleep.types import Command

        assert rulepack.command_apps(Command('FOO=bar git chekout', '')) == \
            frozenset({'git'})
