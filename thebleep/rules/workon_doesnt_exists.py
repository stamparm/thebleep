from thebleep.utils import for_app, replace_command, eager, memoize
from thebleep.system import expanduser
from thebleep.shells import shell


@memoize
@eager
def _get_all_environments():
    root = expanduser('~/.virtualenvs')
    if not root.is_dir():
        return

    for child in root.iterdir():
        if child.is_dir():
            yield child.name


@for_app('workon')
def match(command):
    return (len(command.script_parts) >= 2
            and command.script_parts[1] not in _get_all_environments())


def get_new_command(command):
    misspelled_env = command.script_parts[1]
    # Quoted: this is a word the user typed and it goes back to the shell.
    create_new = u'mkvirtualenv {}'.format(shell.quote(misspelled_env))

    available = _get_all_environments()
    if available:
        return (replace_command(command, misspelled_env, available)
                + [create_new])
    else:
        return create_new


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
