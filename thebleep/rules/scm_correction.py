import os

from thebleep.utils import (command_word_index, for_app, memoize,
                            raw_script_parts)
from thebleep.system import Path

path_to_scm = {
    '.git': 'git',
    '.hg': 'hg',
}

# Spelled out in the decorator below rather than starred from these keys: the
# rule pack reads the app names from the syntax tree, and a name it cannot
# resolve means the rule is consulted for every command there is.
wrong_scm_patterns = {
    'git': 'fatal: Not a git repository',
    'hg': 'abort: no repository found',
}


@memoize
def _get_actual_scm():
    for path, scm in path_to_scm.items():
        if Path(path).is_dir():
            return scm


@for_app('git', 'hg')
def match(command):
    parts = command.script_parts
    scm = os.path.basename(parts[command_word_index(parts)])
    pattern = wrong_scm_patterns[scm]

    return pattern in command.output and _get_actual_scm()


def get_new_command(command):
    scm = _get_actual_scm()
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    if start >= len(parts):
        return scm

    parts[start] = scm
    return ' '.join(parts)
