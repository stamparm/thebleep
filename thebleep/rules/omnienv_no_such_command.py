import re
from thebleep.utils import (cache, command_word_index, for_app,
                            replace_argument, replace_command, which,
                            tool_lines)


# Spelled out in the decorator below rather than starred from this tuple: the
# rule pack reads the app names from the syntax tree, and a name it cannot
# resolve means the rule is consulted for every command there is.
supported_apps = 'goenv', 'nodenv', 'pyenv', 'rbenv'
enabled_by_default = any(which(a) for a in supported_apps)


COMMON_TYPOS = {
    'list': ['versions', 'install --list'],
    'remove': ['uninstall'],
}


@for_app('goenv', 'nodenv', 'pyenv', 'rbenv', at_least=1)
def match(command):
    return 'env: no such command ' in command.output


def get_app_commands(app):
    return [line.strip() for line in tool_lines([app, 'commands'])]


def get_new_command(command):
    found = re.findall(r"env: no such command ['`]([^']*)'", command.output)
    if not found:
        return []
    broken = found[0]
    matched = [replace_argument(command.script, broken, common_typo)
               for common_typo in COMMON_TYPOS.get(broken, [])]

    start = command_word_index(command.script_parts)
    app = command.script_parts[start]
    # Cached under the binary, when there is one to cache under.
    listing = cache(which(app))(get_app_commands) if which(app) \
        else get_app_commands
    app_commands = listing(app)
    matched.extend(replace_command(command, broken, app_commands))
    return matched
