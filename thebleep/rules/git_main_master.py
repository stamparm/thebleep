# -*- encoding: utf-8 -*-

"""`git checkout master` in a repository whose branch is `main`, and back.

The premise is that the branch you named does not exist and the other name
does. That premise has to be *checked*, and it was not: the rule fired on any
git output with `'master'` or `'main'` anywhere in it and rewrote the whole
command line by string substitution. What that came to in practice:

    $ git branch -d master
    error: cannot delete branch 'master' used by worktree at '/tmp/r'
    $ bleep
    git branch -d main          <- a branch nobody named, deleted, one keypress

There the branch does exist -- git's complaint is that it is checked out -- so
the name needed no fixing at all. (`git_branch_delete_checked_out` owns that
error and had gone dead against current git's wording, which is why this rule
was reached at all.)

So the phrases below are the whole of the rule: git saying, in one of the ways
it says it, that the name it was given is not one it knows.

"""

from thebleep.specific.git import git_support
from thebleep.utils import replace_argument

# Every way git says "that is not a thing I have", captured from git 2.30, 2.39
# and 2.47:
#
#   git checkout master   error: pathspec 'master' did not match any file(s)...
#   git branch -d master  error: branch 'master' not found
#   git merge master      merge: master - not something we can merge
#   git rebase master     fatal: invalid upstream 'master'
#   git push origin master  error: src refspec master does not match any
#
# What is deliberately *not* here is any error about a branch that exists --
# `used by worktree at`, `checked out at`, `already exists` -- because there the
# name was right.
UNKNOWN_NAME = (
    'did not match any file(s) known to git',
    'not found',
    'not something we can merge',
    'invalid upstream',
    'does not match any',
    'unknown revision or path not in the working tree',
)


def _swap(output):
    """Which name to put in place of which, or `None` if neither was named."""
    if "'master'" in output or ' master ' in output or 'master -' in output:
        return 'master', 'main'
    if "'main'" in output or ' main ' in output or 'main -' in output:
        return 'main', 'master'
    return None


@git_support
def match(command):
    if not any(phrase in command.output for phrase in UNKNOWN_NAME):
        return False

    swap = _swap(command.output)
    if swap is None:
        return False

    # The name has to be in the command as its own word, or there is nothing
    # here to replace and the suggestion would be the command back again.
    return swap[0] in command.script.split()


@git_support
def get_new_command(command):
    broken, fixed = _swap(command.output)
    # `replace_argument`, not `str.replace`: the latter rewrote every occurrence
    # anywhere in the line, including inside paths and inside other branch names
    # such as `release/master` or `master-fix`.
    return replace_argument(command.script, broken, fixed)


priority = 1200
