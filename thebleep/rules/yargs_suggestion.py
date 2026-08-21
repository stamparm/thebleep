# -*- encoding: utf-8 -*-

"""`eslint --fixx` -> `eslint --fix`, for any tool built with yargs.

The companion to `commander_suggestion`, for the other major Node.js CLI framework.
yargs is used by many modern JavaScript/TypeScript tools (e.g., `webpack`, `vite`,
`ts-node`, `create-react-app`, `nest`, `netlify-cli`, `expo`). When a command or
option is unrecognized, yargs suggests what it thinks you meant:

    $ mytool bulid
    error: unknown command 'bulid'
    Did you mean build?

    $ eslint --fixx .
    error: unknown option: '--fixx'
    Did you mean '--fix'?

    $ mytool tet
    error: unknown command 'tet'
    Did you mean one of test, text?

So this reads yargs rather than reading a tool, and every yargs program is
corrected by it without a line being added here for any of them.

Wordings captured from yargs 17.7.2.

"""

import re
from thebleep.utils import replace_command

# yargs reports unknown commands and options with similar patterns:
# - unknown command 'bulid'
# - unknown option: '--fixx'
UNKNOWN_COMMAND = re.compile(r"unknown command '([^']+)'")
UNKNOWN_OPTION = re.compile(r"unknown option: '--?([^']+)'")

# yargs suggestions:
# - Did you mean build?
# - Did you mean '--fix'?
# - Did you mean one of test, text?
SUGGESTION = re.compile(r"Did you mean (?:one of )?(.+?)\?")

# Fast string literals for rule pack indexing
MARKERS = ('unknown command', 'unknown option', 'Did you mean')


def _broken(output):
    """The word yargs did not recognise."""
    found = UNKNOWN_COMMAND.search(output) or UNKNOWN_OPTION.search(output)
    if found:
        # For options, add back the dashes that were stripped in the regex
        if 'unknown option' in output:
            return '--' + found.group(1)
        return found.group(1)
    return None


def _suggestions(output):
    """The names yargs offered, in the order it offered them."""
    found = SUGGESTION.search(output)
    if not found:
        return []

    # Parse the suggestions - can be single or comma-separated
    suggestions_text = found.group(1).strip()
    # Handle quoted and unquoted suggestions
    suggestions = re.findall(r"'([^']+)'", suggestions_text)
    if not suggestions:
        # Fallback: split by comma if no quotes found
        suggestions = [s.strip() for s in suggestions_text.split(',')]
    
    return suggestions


def match(command):
    return (('unknown command' in command.output
             or 'unknown option' in command.output)
            and 'Did you mean' in command.output
            and bool(_broken(command.output))
            and bool(_suggestions(command.output)))


def get_new_command(command):
    return replace_command(command, _broken(command.output),
                           _suggestions(command.output))
