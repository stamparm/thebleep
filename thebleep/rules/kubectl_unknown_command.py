import re
from thebleep.utils import replace_argument, for_app


# kubectl prints `unknown command "<cmd>"` followed by one or more suggestions:
#
#   error: unknown command "gat" for "kubectl"
#
#   Did you mean this?
#           get
#
# Older kubectl (before 1.26) used slightly different wording but kept the
# `Did you mean` block.
SUGGESTION = re.compile(r'^\s+(\S+)\s*$', re.MULTILINE)


def _get_suggestions(output):
    """Return the commands kubectl itself suggested, in its order."""
    suggestions = []
    after_marker = False
    for line in output.split('\n'):
        if 'Did you mean' in line:
            after_marker = True
            continue
        if not after_marker:
            continue

        m = SUGGESTION.match(line)
        if m:
            suggestions.append(m.group(1))
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

    suggestions = _get_suggestions(command.output)
    if suggestions:
        return [replace_argument(command.script, misspelled_command, s)
                for s in suggestions]

    return []
