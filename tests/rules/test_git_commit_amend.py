# -*- encoding: utf-8 -*-

"""Amending the commit you just made, and not the one that failed.

The rule used to be `'commit' in command.script_parts` and nothing else, so it
answered a *failed* commit with `git commit --amend` -- standing in an
unresolved merge, where `git add` is the answer -- and threw away the message
that had been typed while doing it.

"""

import pytest
from thebleep.rules.git_commit_amend import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def exited(os_environ):
    from thebleep import replay

    def _with(status):
        if status is None:
            os_environ.pop(replay.EXIT_ENV, None)
        else:
            os_environ[replay.EXIT_ENV] = str(status)

    return _with


class TestAfterACommitThatWorked(object):
    @pytest.mark.parametrize('script', [
        'git commit', 'git commit -m "test"', 'git commit -a',
    ])
    def test_it_matches(self, exited, script):
        exited(0)
        assert match(Command(script, '[main abc1234] test\n'))

    @pytest.mark.parametrize('script, expected', [
        ('git commit', 'git commit --amend'),
        ('git commit -m "test commit"',
         'git commit --amend -m "test commit"'),
        ('git commit -a -m x', 'git commit --amend -a -m x'),
    ])
    def test_the_message_survives(self, exited, script, expected):
        """`--amend` goes into the command rather than replacing it. It used to
        answer with the bare string `git commit --amend`, whatever was typed."""
        exited(0)
        assert get_new_command(Command(script, '')) == expected


class TestAfterOneThatFailed(object):
    def test_an_unresolved_merge_is_not_an_amend(self, exited):
        """The case this was reported for. `git add` is the answer; amending is
        not, and neither is dropping the message."""
        exited(1)
        output = ('U\tREADME.md\n'
                  'error: Committing is not possible because you have '
                  'unmerged files.\n')
        assert not match(Command('git commit -m "resolve"', output))

    @pytest.mark.parametrize('status', [1, 2, 128])
    def test_any_failure_at_all(self, exited, status):
        exited(status)
        assert not match(Command('git commit -m x', 'anything\n'))

    def test_and_when_the_shell_did_not_say(self, exited):
        """`None` is not zero. An alias from a release before the status was
        reported does not get a guess -- guessing that a command worked is what
        made this answer a failed one."""
        exited(None)
        assert not match(Command('git commit -m x', ''))


def test_a_different_subcommand(exited):
    exited(0)
    assert not match(Command('git status', ''))
    assert not match(Command('git push', ''))


def test_a_configuration_token_is_not_a_commit(exited):
    exited(0)
    assert not match(Command('git config commit true', ''))
