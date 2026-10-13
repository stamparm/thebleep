"""`systemctl strat ssh` and `systemctl nginx start`.

Two slips, one message. systemd 249 and later say

    Unknown command verb 'strat', did you mean 'start'?

and older ones `Unknown operation 'strat'.` -- this rule wanted the old
wording, so it had not fired on any supported distribution for years, and
nothing read systemd's own suggestion. That suggestion is taken when it is
near the word typed. It is *not* taken for a unit name in the verb's place:
`systemctl nginx start` gets `did you mean 'bind'?`, and the answer there is
the two words the other way round.

Captured from systemd 262 (debian:testing).

"""

import re

from thebleep.shells import shell
from thebleep.specific.sudo import sudo_support
from thebleep.utils import (command_word_index, for_app, get_close_matches,
                            raw_script_parts, replace_argument)

UNKNOWN = re.compile(r"Unknown (?:operation|command verb) '?([^'\s,.]+)")
SUGGESTED = re.compile(r"did you mean '([^']+)'\?")

# The verbs somebody puts after a unit name by mistake.
VERBS = frozenset((
    'start', 'stop', 'restart', 'reload', 'status', 'enable', 'disable',
    'mask', 'unmask', 'is-active', 'is-enabled', 'is-failed', 'show', 'cat',
    'kill', 'try-restart', 'reload-or-restart', 'edit', 'reenable', 'freeze',
    'thaw', 'clean', 'help', 'list-dependencies'))


@sudo_support
@for_app('systemctl')
def match(command):
    return 'Unknown ' in command.output and bool(_fixes(command))


@sudo_support
def get_new_command(command):
    return _fixes(command)


def _fixes(command):
    unknown = UNKNOWN.search(command.output)
    if unknown is None:
        return []
    broken = unknown.group(1)
    parts = command.script_parts
    start = command_word_index(parts)
    arguments = parts[start + 1:]

    suggestions = []
    if len(arguments) == 2 and arguments[0] == broken \
            and arguments[1] in VERBS:
        raw = raw_script_parts(command.script)
        if len(raw) == len(parts):
            raw[-1], raw[-2] = raw[-2], raw[-1]
            suggestions.append(' '.join(raw))
    suggested = SUGGESTED.search(command.output)
    if suggested and get_close_matches(broken, [suggested.group(1)], 1):
        suggestions.append(replace_argument(
            command.script, broken, shell.quote(suggested.group(1))))
    return suggestions
