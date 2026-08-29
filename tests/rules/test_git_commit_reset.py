# -*- encoding: utf-8 -*-

"""Offering to throw a commit away, and when not to.

This rule used to be `'commit' in command.script_parts` and nothing else, so it
fired on every `git commit` that *failed* -- and every failed commit is a commit
that has not happened, so the thing it offered to undo was the one before it:

    $ git commit -m "the fix"
    pre-commit hook failed: 3 lint errors
    $ bleep
    git reset HEAD~           <- drops the commit before this one

It now wants the commit to have worked, which is the moment it exists for.

"""

import pytest
from thebleep import replay
from thebleep.rules.git_commit_reset import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def exited(os_environ):
    def _with(status):
        os_environ[replay.EXIT_ENV] = str(status)

    return _with


@pytest.mark.parametrize('script', [
    'git commit -m "test"', 'git commit'])
def test_a_commit_that_worked(exited, script):
    exited(0)
    assert match(Command(script, ''))


@pytest.mark.parametrize('status', [1, 2, 128])
def test_a_commit_that_failed_is_not_undone(exited, status):
    """A failed hook, unmerged files, a stale index lock: none of them is this
    rule's business, and each left the previous commit one keystroke from
    gone."""
    exited(status)
    assert not match(Command('git commit -m "the fix"',
                             'pre-commit hook failed'))


def test_a_shell_that_did_not_say(os_environ):
    """An alias from a release before the status was reported. Guessing that a
    commit worked is what got the commit before it discarded."""
    os_environ.pop(replay.EXIT_ENV, None)
    assert not match(Command('git commit -m x', ''))


@pytest.mark.parametrize('script', [
    'git branch foo',
    'git checkout feature/test_commit',
    'git push'])
def test_not_match(exited, script):
    exited(0)
    assert not match(Command(script, ''))


def test_a_configuration_token_is_not_a_commit(exited):
    exited(0)

    assert not match(Command('git config commit true', ''))


def test_a_commit_after_environment_assignments_still_matches(exited):
    exited(0)

    assert match(Command('GIT_OPTIONAL_LOCKS=0 git commit', ''))


@pytest.mark.parametrize('script', [
    ('git commit -m "test commit"'),
    ('git commit')])
def test_get_new_command(script):
    assert get_new_command(Command(script, '')) == 'git reset HEAD~'


def test_it_needs_no_output():
    """The exit status and the command are the whole question, so this still
    works when the previous command is not re-read."""
    from thebleep.rules import git_commit_reset

    assert git_commit_reset.requires_output is False
