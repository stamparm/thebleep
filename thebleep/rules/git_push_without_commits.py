import re
from thebleep.shells import shell
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.utils import replace_argument


@git_support
def match(command):
    index = git_subcommand_index(command.script_parts)
    return (command.script_parts[index:index + 1] == ['push']
            and bool(re.search(r"src refspec \w+ does not match any",
                               command.output)))


def get_new_command(command):
    marker = 'commit -m "Initial commit"'
    commit = replace_argument(command.script, 'push', marker)
    commit = commit[:commit.index(marker) + len(marker)]
    return shell.and_(commit, command.script)
