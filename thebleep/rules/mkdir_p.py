import re
from thebleep.specific.sudo import sudo_support
from thebleep.utils import is_app


def _makes_directories(command):
    """Whether this is a directory being made at all.

    `'mkdir' in command.script` was not: it matched `echo mkdir`,
    `git mkdir-x` and `python mkdirs.py`, and offered each of them back
    unchanged as a correction.

    """
    if is_app(command, 'mkdir', at_least=1):
        return True

    # Hadoop's file system commands: `hdfs dfs -mkdir <path>`.
    return is_app(command, 'hdfs') and '-mkdir' in command.script_parts


@sudo_support
def match(command):
    return (_makes_directories(command)
            and 'No such file or directory' in command.output)


@sudo_support
def get_new_command(command):
    return re.sub('\\bmkdir (.*)', 'mkdir -p \\1', command.script)
