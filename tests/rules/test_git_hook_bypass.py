# -*- encoding: utf-8 -*-

"""Offering `--no-verify`, and when not to.

This rule used to fire on any `git am`, `git commit` or `git push`, and with
`requires_output = False` it did not need to see what went wrong. So declining
to re-run your command -- which leaves no output for anything else to match on
-- was answered with `git push --no-verify`: a suggestion that says a hook
failed when none ran, and the one suggestion in the list with consequences.

It now needs the output, and needs an executable hook to exist for the
subcommand in question. A repository with no hooks cannot have had one fail.

"""

import pytest
from thebleep.rules import git_hook_bypass
from thebleep.rules.git_hook_bypass import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def hooks(mocker):
    """Which hooks this repository has, without one on disk."""
    def _installed(*names):
        # `os.path.basename`, not `path.split('/')`: the rule builds the path
        # with `os.path.join`, which uses a backslash on Windows -- so splitting
        # on a forward slash found nothing there and this test failed on every
        # Windows job while passing here. The third time that assumption has
        # been made in this suite.
        import os

        mocker.patch.object(git_hook_bypass, '_hooks_directory',
                            return_value=os.path.join('repo', '.git', 'hooks'))
        mocker.patch('os.path.isfile',
                     side_effect=lambda path: os.path.basename(path) in names)
        mocker.patch('os.access', return_value=True)

    return _installed


@pytest.fixture
def no_hooks(mocker):
    return mocker.patch.object(git_hook_bypass, '_hooks_directory',
                               return_value=None)


class TestWhenAHookCouldHaveRun(object):
    @pytest.mark.parametrize('script', [
        'git commit', "git commit -m 'foo bar'", 'git commit --amend',
    ])
    def test_a_commit_with_a_commit_hook(self, hooks, script):
        hooks('pre-commit')
        assert match(Command(script, 'lint failed\n'))

    def test_a_push_with_a_push_hook(self, hooks):
        hooks('pre-push')
        assert match(Command('git push -u origin main', 'push hook failed\n'))

    def test_an_am_with_an_am_hook(self, hooks):
        hooks('applypatch-msg')
        assert match(Command('git am patch', 'rejected\n'))

    @pytest.mark.parametrize('script, expected', [
        ('git commit', 'git commit --no-verify'),
        ("git commit -m 'foo bar'", "git commit --no-verify -m 'foo bar'"),
        ('git push -u foo bar', 'git push --no-verify -u foo bar'),
    ])
    def test_what_it_offers(self, hooks, script, expected):
        hooks('pre-commit', 'pre-push')
        assert get_new_command(Command(script, 'failed\n')) == expected


class TestWhenNoHookCould(object):
    def test_a_repository_with_no_hooks(self, no_hooks):
        """Nothing to bypass, so nothing to say."""
        assert not match(Command('git commit -m x', 'lint failed\n'))
        assert not match(Command('git push', 'anything\n'))

    def test_a_hook_for_a_different_subcommand(self, hooks):
        """A `pre-push` hook says nothing about why a commit failed."""
        hooks('pre-push')
        assert not match(Command('git commit -m x', 'failed\n'))

    @pytest.mark.parametrize('script', [
        'git add foo', 'git status', 'git diff foo bar',
        'git config commit.gpgsign true',
        'git config push.default simple',
    ])
    def test_a_subcommand_that_runs_no_hooks(self, hooks, script):
        hooks('pre-commit', 'pre-push')
        assert not match(Command(script, 'anything\n'))

    def test_global_option_value_is_not_the_subcommand(self, hooks):
        hooks('pre-commit')
        assert not match(Command('git -c alias.commit=show config',
                                 'anything\n'))


def test_it_needs_the_output():
    """The whole reason `requires_output` was turned on.

    With it off, this was the only rule that could match a command whose output
    nobody had -- so declining to re-run your command was answered by offering
    to skip your own pre-commit checks.

    """
    assert git_hook_bypass.__dict__.get('requires_output', True) is True


def test_it_comes_after_the_rules_that_know_what_happened():
    """`git push` with no upstream has a right answer, and this is not it.

    git prints nothing of its own when a hook fails -- only what the hook
    printed -- so there is no marker to match on and no way to be sure. That is
    a reason to be an option further down the list rather than the first thing
    offered.

    """
    from thebleep import const

    assert git_hook_bypass.priority > const.DEFAULT_PRIORITY
