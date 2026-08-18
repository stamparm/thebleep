import re
import subprocess
from thebleep import utils
from thebleep.utils import replace_argument
from thebleep.specific.git import git_support
from thebleep.shells import shell


MISSING = re.compile(r"error: pathspec '([^']*)' "
                     r"did not match any file\(s\) known to git")


@git_support
def match(command):
    # The name has to be readable, not just the message. A pathspec containing
    # a quote does not come back out of that regex, and this used to match
    # anyway and leave `get_new_command` raising IndexError.
    return ('did not match any file(s) known to git' in command.output
            and "Did you forget to 'git add'?" not in command.output
            and MISSING.search(command.output) is not None)


def get_branches():
    proc = subprocess.Popen(
        ['git', 'branch', '-a', '--no-color', '--no-column'],
        stdout=subprocess.PIPE)
    for line in proc.stdout.readlines():
        line = line.decode('utf-8')
        if '->' in line:    # Remote HEAD like b'  remotes/origin/HEAD -> origin/master'
            continue
        if line.startswith('*'):
            line = line.split(' ')[1]
        if line.strip().startswith('remotes/'):
            line = '/'.join(line.split('/')[2:])
        yield line.strip()


@git_support
def get_new_command(command):
    missing_file = MISSING.search(command.output).group(1)
    closest_branch = utils.get_closest(missing_file, get_branches(),
                                       fallback_to_first=False)

    new_commands = []

    if closest_branch:
        # Quoted. A branch name is allowed to contain `;`, `&&`, `|`, backticks
        # and `$(...)`: git rejects spaces and a handful of other characters and
        # accepts the rest. So a repository can carry a branch called
        # `feature;rm -rf ~`, and this went back to the shell to be evaluated.
        new_commands.append(replace_argument(command.script, missing_file,
                                             shell.quote(closest_branch)))
    if len(command.script_parts) > 1 and command.script_parts[1] == 'checkout':
        new_commands.append(replace_argument(command.script, 'checkout', 'checkout -b'))

    if not new_commands:
        new_commands.append(shell.and_('git branch {}', '{}').format(
            shell.quote(missing_file), command.script))

    return new_commands
