import re
from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import replace_argument, tool_output


def _has_no_commits(command, index):
    """Whether git itself says this repository has no commits yet.

    `src refspec X does not match any` is also what a typo in the branch name
    prints in a repository with plenty of commits, and there the answer used
    to be the same -- `git commit -m "Initial commit" && git push origin
    mastr`, at 95% and low risk, so `auto_run_confidence` committed whatever
    was staged and pushed a new branch. Only git's own word that the branch
    has no commits counts; a probe that could not run is not that word.

    """
    said = tool_output(command.script_parts[:index] + ['log', '-1', '--oneline'],
                       merge_stderr=True)
    return 'does not have any commits yet' in said


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['push']
            and bool(re.search(r"src refspec \S+ does not match any",
                               command.output))
            and _has_no_commits(command, index))


@git_support
def get_new_command(command):
    marker = 'commit -m "Initial commit"'
    commit = replace_argument(command.script, 'push', marker)
    if marker not in commit:
        return []
    commit = commit[:commit.index(marker) + len(marker)]
    return shell.and_(commit, command.script)
