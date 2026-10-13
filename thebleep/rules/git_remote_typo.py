"""`git push orign main`, `git pull origin mian`, `git push origin mastr`.

    $ git push orign main
    fatal: 'orign' does not appear to be a git repository
    $ git pull origin mian
    fatal: couldn't find remote ref mian
    $ git push origin mastr
    error: src refspec mastr does not match any

A remote name, a branch on the remote, a local branch: each a slip in a name
git already has -- `git remote`, the `refs/remotes/<remote>/` git fetched
last, `git branch`. Nothing is asked of the network. Captured from git 2.53.0.

"""

import re

from thebleep import matching
from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import replace_argument, tool_lines

NOT_A_REMOTE = re.compile(r"fatal: '([^']+)' does not appear to be a git "
                          r"repository")
NO_REMOTE_REF = re.compile(r"fatal: couldn't find remote ref (\S+)")
NO_LOCAL_REF = re.compile(r"error: src refspec (\S+) does not match any")
TRANSFERS = ('push', 'pull', 'fetch')


def _transfer(command):
    parts = command.script_parts
    index = git_subcommand_index(parts)
    return parts[index:index + 1] and parts[index] in TRANSFERS


def _remote_branches(remote):
    prefix = remote + '/'
    return [line.strip()[len(prefix):] for line in tool_lines(
        ['git', 'branch', '-r', '--no-color', '--format=%(refname:short)'])
        if line.strip().startswith(prefix)]


def _broken_and_candidates(command):
    parts = command.script_parts
    found = NOT_A_REMOTE.search(command.output)
    if found and found.group(1) in parts:
        return found.group(1), tool_lines(['git', 'remote'])
    found = NO_REMOTE_REF.search(command.output)
    if found and found.group(1) in parts:
        index = parts.index(found.group(1))
        remote = parts[index - 1] if index > 0 else 'origin'
        return found.group(1), _remote_branches(remote)
    found = NO_LOCAL_REF.search(command.output)
    if found and found.group(1) in parts:
        # An empty repository has no branches to offer, and there
        # `git_push_without_commits` is the answer.
        return found.group(1), tool_lines(
            ['git', 'branch', '--no-color', '--format=%(refname:short)'])
    return None, []


@git_support
def match(command):
    return (_transfer(command)
            and ('does not appear to be a git repository' in command.output
                 or "couldn't find remote ref" in command.output
                 or 'does not match any' in command.output)
            and bool(_broken_and_candidates(command)[0]))


@git_support
def get_new_command(command):
    broken, candidates = _broken_and_candidates(command)
    if broken is None:
        return []
    # Quoted: a branch can be called anything git allows, `;` included.
    return [replace_argument(command.script, broken, shell.quote(name))
            for name in matching.rank(broken, candidates, limit=3)]
