from collections import Counter
import re
from thebleep.system import expanduser
from thebleep.utils import (get_valid_history_without_current,
                            memoize, replace_argument)
from thebleep.shells import shell


patterns = [r'no such file or directory: (.*)$',
            r"cannot access '(.*)': No such file or directory",
            r': (.*): No such file or directory',
            r"can't cd to (.*)$"]


@memoize
def _get_destination(command):
    for pattern in patterns:
        found = re.findall(pattern, command.output)
        if found:
            if found[0] in command.script_parts:
                return found[0]


def match(command):
    return bool(_get_destination(command))


def _get_all_absolute_paths_from_history(command):
    counter = Counter()

    for line in get_valid_history_without_current(command):
        splitted = shell.split_command(line)

        for param in splitted[1:]:
            if param.startswith('/') or param.startswith('~'):
                if param.endswith('/'):
                    param = param[:-1]

                counter[param] += 1

    return (path for path, _ in counter.most_common(None))


def _quoted(path):
    """`path` as a word the shell will read back as this path.

    These come out of the user's own history, so they carry whatever a
    filesystem allows: a space, a `$`, a backtick, a `;`. Unquoted, those went
    back to the shell as syntax rather than as a name.

    The leading `~` stays *outside* the quotes, because that is the one
    character here whose meaning the shell is meant to change. `'~/work'` is a
    literal directory called `~`, which is not where anybody keeps their work.

    """
    if path.startswith('~/'):
        return '~/' + shell.quote(path[2:])
    if path == '~':
        return path

    return shell.quote(path)


def get_new_command(command):
    destination = _get_destination(command)
    paths = _get_all_absolute_paths_from_history(command)

    return [replace_argument(command.script, destination, _quoted(path))
            for path in paths if path.endswith(destination)
            and expanduser(path).exists()]


priority = 800
