# -*- encoding: utf-8 -*-

"""Swapping `master` for `main` and back, but only when the name is unknown.

Every fixture here was printed by a real git -- 2.30.2, 2.39.5 and 2.47.3 all
agree on the wordings below except where noted. That matters more than usual for
this rule: it used to fire on any git output with `'master'` in it, and the
output it most wanted watching was one where the branch existed.

"""

import pytest
from thebleep.rules.git_main_master import match, get_new_command
from thebleep.types import Command

# The name is not one git has. These are the cases the rule is for.
PATHSPEC = "error: pathspec '{}' did not match any file(s) known to git\n"
NOT_FOUND = "error: branch '{}' not found\n"
NOT_MERGEABLE = 'merge: {} - not something we can merge\n'
BAD_UPSTREAM = "fatal: invalid upstream '{}'\n"

# The name *is* one git has, and git is complaining about something else. The
# rule must keep its hands off: `git branch -d master` used to become
# `git branch -d main`, which deleted a branch nobody had named.
IN_USE = "error: cannot delete branch '{}' used by worktree at '/tmp/r'\n"
IN_USE_OLD = "error: Cannot delete branch '{}' checked out at '/tmp/r'\n"
ALREADY_EXISTS = "fatal: a branch named '{}' already exists\n"


class TestTheNameIsUnknown(object):
    @pytest.mark.parametrize('script, output', [
        ('git checkout master', PATHSPEC.format('master')),
        ('git checkout main', PATHSPEC.format('main')),
        ('git show main', PATHSPEC.format('main')),
        ('git branch -d master', NOT_FOUND.format('master')),
        ('git merge master', NOT_MERGEABLE.format('master')),
        ('git rebase master', BAD_UPSTREAM.format('master')),
    ])
    def test_it_matches(self, script, output):
        assert match(Command(script, output))

    @pytest.mark.parametrize('script, output, expected', [
        ('git checkout master', PATHSPEC.format('master'),
         'git checkout main'),
        ('git checkout main', PATHSPEC.format('main'), 'git checkout master'),
        ('git merge master', NOT_MERGEABLE.format('master'),
         'git merge main'),
        ('git rebase master', BAD_UPSTREAM.format('master'),
         'git rebase main'),
    ])
    def test_it_swaps_the_name(self, script, output, expected):
        assert get_new_command(Command(script, output)) == expected


class TestTheNameExists(object):
    """The rule's premise is that the branch is not there. When git says it is,
    there is nothing to rename and renaming it destroys something."""

    @pytest.mark.parametrize('output', [
        IN_USE.format('master'),
        IN_USE_OLD.format('master'),
        ALREADY_EXISTS.format('master'),
    ])
    def test_deleting_a_branch_that_exists_is_not_a_renaming(self, output):
        # Reproduced end to end before this was fixed: the suggestion was
        # `git branch -d main`, and accepting it deleted `main`.
        assert not match(Command('git branch -d master', output))

    def test_the_worktree_error_is_left_to_the_rule_that_owns_it(self):
        """`git_branch_delete_checked_out`, which had gone dead against
        current git and is why this rule was reached at all."""
        from thebleep.rules import git_branch_delete_checked_out as owner

        command = Command('git branch -d master', IN_USE.format('master'))
        assert owner.match(command)
        assert not match(command)


class TestNotMatching(object):
    @pytest.mark.parametrize('script, output', [
        # Nothing printed, so nothing to go on.
        ('git checkout master', ''),
        ('git checkout main', ''),
        # A name that is neither.
        ('git checkout wibble', PATHSPEC.format('wibble')),
        # `master` is in the output but not a word of the command, so there is
        # nothing to replace and the suggestion would be the command back.
        ('git status', PATHSPEC.format('master')),
    ])
    def test_it_does_not_match(self, script, output):
        assert not match(Command(script, output))

    def test_the_name_is_replaced_as_a_word_and_not_as_a_substring(self):
        """`str.replace` rewrote every occurrence anywhere in the line, so a
        path or a branch called `release/master-fix` was rewritten too."""
        command = Command('git checkout release/master-fix',
                          PATHSPEC.format('release/master-fix'))
        assert not match(command)
