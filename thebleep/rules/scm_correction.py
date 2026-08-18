from thebleep.utils import for_app, memoize
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
    scm = command.script_parts[0]
    pattern = wrong_scm_patterns[scm]

    return pattern in command.output and _get_actual_scm()


def get_new_command(command):
    scm = _get_actual_scm()
    return u' '.join([scm] + command.script_parts[1:])
