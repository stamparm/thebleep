from subprocess import CalledProcessError, check_output
from thebleep.shells import shell
from thebleep.specific.git import git_support
from thebleep.utils import DEVNULL, memoize, replace_argument

# Where to move to before deleting the branch we are standing on. `master` is
# only a guess, and a wrong one in any repository made since 2020.
FALLBACK_BRANCH = 'master'


def _git(*arguments):
    try:
        return check_output(('git',) + arguments,
                            stderr=DEVNULL).decode('utf-8', 'replace').strip()
    except (OSError, CalledProcessError):
        return ''


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


@git_support
def match(command):
    return (
        ("branch -d" in command.script or "branch -D" in command.script)
        and "error: Cannot delete branch '" in command.output
        and "' checked out at '" in command.output
    )


@git_support
def get_new_command(command):
    # The branch name is quoted: it comes from the repository, by way of
    # `origin/HEAD`, and git is happy for a branch to be called
    # `main;rm -rf ~`.
    return shell.and_(
        u"git checkout {}".format(shell.quote(_default_branch())),
        replace_argument(command.script, "-d", "-D"))
