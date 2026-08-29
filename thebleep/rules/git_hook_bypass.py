# -*- encoding: utf-8 -*-

"""A `git commit` or `git push` a hook refused -> offer to skip the hook.

Useful when a hook really did stop you. What it used to do was fire on *any*
`git am`, `git commit` or `git push`, with `requires_output = False` so it did
not even need to see what went wrong -- which had two consequences, and the
second one is the reason this file was rewritten.

    $ git push
    fatal: The current branch topic has no upstream branch.
    $ bleep
    git push has to run again to be read... Run it? [y/N] no

    git push --no-verify

Declining to re-run the command left this as the *only* rule that could match,
so caution was answered with `--no-verify`. The suggestion is also a lie: no
hook ran, none failed, and `--no-verify` says one did. And it is the one
suggestion in that list with consequences -- somebody who said "no, do not
re-run my command" and then pressed enter had skipped their own pre-commit
checks.

So: it needs the output now, which is what stops it being the answer to a
declined replay. And it asks whether a hook could have run at all -- an
executable hook for this subcommand, wherever `core.hooksPath` puts them. A
repository with no hooks cannot have had one fail.

That is as far as evidence goes: git prints nothing of its own when a hook
fails, only whatever the hook printed, so there is no marker to match on. Which
is why this also sits *after* the ordinary rules rather than in front of them --
`git push` with no upstream is answered by the rule that knows that, and this is
something to arrow down to.

"""

from thebleep.utils import replace_argument
from thebleep.specific.git import git_subcommand_index, git_support

# The subcommands that consult a hook, and the hooks each one runs.
HOOKED = {
    'am': ('applypatch-msg', 'pre-applypatch', 'post-applypatch'),
    'commit': ('pre-commit', 'prepare-commit-msg', 'commit-msg',
               'post-commit'),
    'push': ('pre-push',),
}


def _subcommand(script_parts):
    index = git_subcommand_index(script_parts)
    return (script_parts[index]
            if index < len(script_parts) and script_parts[index] in HOOKED
            else None)


def _hooks_directory():
    """Where this repository keeps its hooks, or `None`.

    Asked of git rather than assumed to be `.git/hooks`, because
    `core.hooksPath` moves it -- and a project that sets it is exactly the sort
    that has hooks worth bypassing.

    """
    import os
    from thebleep.utils import tool_output

    # Not a repository, no git, a timeout: `tool_output` answers `''` to all of
    # them, and either way there is no hooks directory to find.
    path = tool_output(('git', 'rev-parse', '--git-path', 'hooks')).strip()
    return path if path and os.path.isdir(path) else None


def _has_a_hook(subcommand):
    """Whether an executable hook this subcommand runs is actually there."""
    import os

    directory = _hooks_directory()
    if directory is None:
        return False

    for name in HOOKED[subcommand]:
        path = os.path.join(directory, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return True

    return False


@git_support
def match(command):
    subcommand = _subcommand(command.script_parts)
    return subcommand is not None and _has_a_hook(subcommand)


@git_support
def get_new_command(command):
    subcommand = _subcommand(command.script_parts)
    return replace_argument(command.script, subcommand,
                            subcommand + ' --no-verify')


# After the rules that know what the error actually was. `git push` with no
# upstream has a right answer, and this is not it.
priority = 4000
