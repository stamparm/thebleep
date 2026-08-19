# -*- encoding: utf-8 -*-

"""`kubectl gat pods` -> `kubectl get pods`.

kubectl names the word it did not understand and then lists what it might have
been, which is more than most tools do:

    error: unknown command "gat" for "kubectl"

    Did you mean this?
        set
        get
        wait

kubectl indents those with a tab; they are spaces above so that this file has
none in it. Its order is not the useful order -- `get` is second there -- so the
suggestions are sorted by how close each is to what was typed. `replace_command`
does that, and quotes what it puts back: the words come out of another program's
output, and a suggestion is evaluated by the shell once it is accepted.

Sometimes there is no `Did you mean` block at all (`kubectl zzzzzz`), and then
there is nothing to suggest.

"""

import re
from thebleep.utils import for_app, replace_command

# A suggestion is an indented word on a line of its own. kubectl indents with a
# tab; the guard against reading the rest of the message as suggestions is that
# anything else non-blank ends the block.
SUGGESTION = re.compile(r'^\s+(\S+)\s*$')


def _get_suggestions(output):
    """The commands kubectl itself offered, in the order it printed them."""
    suggestions = []
    after_marker = False
    for line in output.split('\n'):
        if 'Did you mean' in line:
            after_marker = True
            continue
        if not after_marker:
            continue

        found = SUGGESTION.match(line)
        if found:
            suggestions.append(found.group(1))
        elif line.strip():
            # The suggestions are over.
            break

    return suggestions


@for_app('kubectl', at_least=1)
def match(command):
    return 'unknown command' in command.output


def get_new_command(command):
    # The mistyped subcommand is the first non-flag argument after `kubectl`.
    misspelled_command = command.script_parts[1]

    return replace_command(command, misspelled_command,
                           _get_suggestions(command.output))
