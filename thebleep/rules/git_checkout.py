import re
from thebleep import utils
from thebleep.utils import replace_argument, tool_lines
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.shells import shell


MISSING = re.compile(r"error: pathspec '([^']*)' "
                     r"did not match any file\(s\) known to git")
# `git switch featuer`, git 2.23 onwards -- `switch` says it differently, and
# nothing read it.
INVALID_REFERENCE = re.compile(r"^fatal: invalid reference: (.+)$", re.MULTILINE)


@git_support
def match(command):
    # The name has to be readable, not just the message. A pathspec containing
    # a quote does not come back out of that regex, and this used to match
    # anyway and leave `get_new_command` raising IndexError.
    if 'invalid reference: ' in command.output:
        parts = command.script_parts
        index = git_subcommand_index(parts)
        return (parts[index:index + 1] == ['switch']
                and INVALID_REFERENCE.search(command.output) is not None)
    found = MISSING.search(command.output)
    # `-` is no branch git would create: `git commit - m x` is a stray
    # space, and `git branch - && ...` was offered for it.
    return ('did not match any file(s) known to git' in command.output
            and "Did you forget to 'git add'?" not in command.output
            and found is not None and not found.group(1).startswith('-'))


def get_branches():
    for line in tool_lines(
            ['git', 'branch', '-a', '--no-color', '--no-column']):
        if '->' in line:    # Remote HEAD like b'  remotes/origin/HEAD -> origin/master'
            continue
        if line.startswith('*'):
            line = line.split(' ')[1]
        if line.strip().startswith('remotes/'):
            line = '/'.join(line.split('/')[2:])
        yield line.strip()


# The other name for the default branch: `git checkout master` in a repository
# that only has `main` wants `main`, not a new branch called `master`.
COUNTERPART = {'master': 'main', 'main': 'master'}


@git_support
def get_new_command(command):
    found = MISSING.search(command.output) \
        or INVALID_REFERENCE.search(command.output)
    missing_file = found.group(1)
    branches = list(get_branches())
    if COUNTERPART.get(missing_file) in branches:
        closest_branch = COUNTERPART[missing_file]
    else:
        closest_branch = utils.get_closest(missing_file, branches,
                                           fallback_to_first=False)

    new_commands = []

    if closest_branch:
        # Quoted. A branch name is allowed to contain `;`, `&&`, `|`, backticks
        # and `$(...)`: git rejects spaces and a handful of other characters and
        # accepts the rest. So a repository can carry a branch called
        # `feature;rm -rf ~`, and this went back to the shell to be evaluated.
        new_commands.append(replace_argument(command.script, missing_file,
                                             shell.quote(closest_branch)))
    if not utils._tool_probe_state().get():
        # The branches were never asked for: `--json`, MCP and the agent hooks
        # turn probes off. Then "create it" is not an answer anybody has
        # grounds for -- `git checkout mastr` came out as `git checkout -b
        # mastr` at 95%. (An empty list with probes on is a repository with no
        # commits yet, where creating the branch is exactly right.)
        return new_commands
    if COUNTERPART.get(missing_file) in branches:
        return new_commands
    index = git_subcommand_index(command.script_parts)
    subcommand = command.script_parts[index:index + 1]
    if subcommand == ['checkout']:
        new_commands.append(replace_argument(command.script, 'checkout', 'checkout -b'))
    elif subcommand == ['switch']:
        new_commands.append(replace_argument(command.script, 'switch', 'switch -c'))

    if not new_commands:
        new_commands.append(shell.and_(
            u'git branch {}'.format(shell.quote(missing_file)),
            command.script))

    return new_commands
