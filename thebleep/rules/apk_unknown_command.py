# -*- encoding: utf-8 -*-

"""`apk isntall vim` -> `apk add vim`, on Alpine.

apk names the word it did not know and offers nothing else:

    ERROR: 'isntall' is not an apk command. See 'apk --help'.

The candidates come from `apk --help`, whose command lines are two spaces, a
name, and a description -- captured from apk-tools 3.0.6 and, in the same
shape, from 2.14. `isntall` finds nothing close among them by spelling alone,
so the everyday verbs other package managers use are mapped to apk's own
before the spelling is compared: `install` is `add`, `remove` is `del`.

"""

import re
from thebleep.specific.sudo import sudo_support
from thebleep.utils import (for_app, get_close_matches, replace_argument,
                            replace_command, tool_output, which)

enabled_by_default = bool(which('apk'))

UNKNOWN = re.compile(r"'([^']+)' is not an apk command")
COMMAND_LINE = re.compile(r'^  ([a-z][a-z0-9-]*) {2,}\S', re.MULTILINE)

# What people type after using every other package manager, and what apk
# calls it.
SYNONYMS = {
    'install': 'add', 'remove': 'del', 'uninstall': 'del', 'erase': 'del',
    'purge': 'del', 'refresh': 'update', 'find': 'search', 'show': 'info',
    'ls': 'list', 'get': 'fetch', 'download': 'fetch', 'dist-upgrade': 'upgrade',
}


@sudo_support
@for_app('apk')
def match(command):
    return 'is not an apk command' in command.output


def _parse_operations(help_text):
    return COMMAND_LINE.findall(help_text)


def _get_operations():
    return _parse_operations(tool_output(['apk', '--help']))


def _through_synonyms(broken, operations):
    """The apk verb for a word that is one of another manager's verbs, or a
    slip of one: `isntall` is close to `install`, and `install` is `add`."""
    close = get_close_matches(broken, list(SYNONYMS), n=1, cutoff=0.8)
    if close and SYNONYMS[close[0]] in operations:
        return SYNONYMS[close[0]]
    return None


@sudo_support
def get_new_command(command):
    found = UNKNOWN.search(command.output)
    if not found:
        return []
    broken = found.group(1)
    operations = _get_operations()
    if not operations:
        return []
    by_spelling = replace_command(command, broken, operations)
    synonym = _through_synonyms(broken, operations)
    if synonym:
        # `add` is nothing like `isntall` by spelling, so it would not be in
        # the list at all, let alone first.
        first = replace_argument(command.script, broken, synonym)
        return [first] + [fixed for fixed in by_spelling if fixed != first]
    return by_spelling
