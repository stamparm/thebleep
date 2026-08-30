from thebleep.utils import (command_word_index, for_app, replace_command,
                            eager, memoize)
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
    parts = command.script_parts
    start = command_word_index(parts)
    return (len(parts) > start + 1
            and parts[start + 1] not in _get_all_environments())


def get_new_command(command):
    parts = command.script_parts
    misspelled_env = parts[command_word_index(parts) + 1]
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
