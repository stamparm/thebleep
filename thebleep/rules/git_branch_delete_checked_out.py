import re
from thebleep.shells import shell
from thebleep.specific.git import git_support
from thebleep.utils import memoize, replace_argument, tool_output

# Where to move to before deleting the branch we are standing on. `master` is
# only a guess, and a wrong one in any repository made since 2020.
FALLBACK_BRANCH = 'master'


def _git(*arguments):
    # Through `tool_output`, which is where the timeout is: a `git` against a
    # repository on a stuck network mount answers when the mount does, and a
    # rule that never returns is The Bleep frozen at the prompt.
    return tool_output(('git',) + arguments).strip()


@memoize
def _default_branch():
    """The repository's own default branch, asked of the repository."""
    # What `git clone` would have checked out.
    head = _git('symbolic-ref', '--short', 'refs/remotes/origin/HEAD')
    if head:
        return head.rsplit('/', 1)[-1]

    # No remote, or no HEAD recorded for it, so fall back to whichever of the
    # usual names this repository actually has.
    for name in ('main', FALLBACK_BRANCH):
        if _git('rev-parse', '--verify', '--quiet', 'refs/heads/' + name):
            return name

    return FALLBACK_BRANCH


# git 2.45 and older:  error: Cannot delete branch 'x' checked out at '/path'
# git 2.46 and newer:  error: cannot delete branch 'x' used by worktree at '/path'
#
# Both the capital and the phrase changed, and this matched only the old form --
# so on any current git the rule went dead, `git_main_master` answered the error
# instead, and `git branch -d master` became `git branch -d main`. Captured from
# git 2.30.2, 2.39.5 and 2.47.3.
CHECKED_OUT = re.compile(
    r"error: cannot delete branch '.+' "
    r"(?:checked out|used by worktree) at '", re.IGNORECASE)


@git_support
def match(command):
    return (("branch -d" in command.script or "branch -D" in command.script)
            and bool(CHECKED_OUT.search(command.output)))


@git_support
def get_new_command(command):
    # The branch name is quoted: it comes from the repository, by way of
    # `origin/HEAD`, and git is happy for a branch to be called
    # `main;rm -rf ~`.
    return shell.and_(
        u"git checkout {}".format(shell.quote(_default_branch())),
        replace_argument(command.script, "-d", "-D"))
