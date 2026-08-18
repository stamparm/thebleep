import re
from thebleep.specific.sudo import sudo_support
from thebleep.utils import is_app


def _removes_files(command):
    """Whether this is a file removal at all.

    `'rm' in command.script` was not: it matched `confirm build`, `charm .`,
    `/usr/bin/rmdir x` and, worse, `git rm cached`, which it then offered to
    turn into `git rm -rf cached`.

    """
    if is_app(command, 'rm', at_least=1):
        return True

    # Hadoop's file system commands: `hdfs dfs -rm <path>`.
    return is_app(command, 'hdfs') and '-rm' in command.script_parts


@sudo_support
def match(command):
    return (_removes_files(command)
            and 'is a directory' in command.output.lower())


@sudo_support
def get_new_command(command):
    # `-r` and not `-rf`. `-r` is what makes the removal recursive and is enough
    # to remove a directory; `-f` additionally suppresses the prompt for a
    # write-protected file and the complaint about a path that is not there,
    # which is exactly the confirmation somebody may want to see. Adding it
    # would be this rule choosing to remove more quietly than it was asked to.
    return re.sub(r'\brm (.*)', r'rm -r \1', command.script)
