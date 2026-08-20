"""Fixes a command whose quoting was closed with the wrong character.

    git commit -m 'My Message"

The test used to be that both quote characters appear somewhere in the script,
and the fix was to replace every `'` with a `"`. Both halves of that were wrong
in the same way: a command containing both kinds of quote is usually a perfectly
good command, and rewriting its quotes breaks it.

    git commit -m "it's fine"   ->   git commit -m "it"s fine"
    echo "don't"                ->   echo "don"t"

So the rule now only fires when the script really cannot be parsed as it stands
and swapping the quotes makes it parse. That is a narrow claim about a specific
mistake, and it can be checked rather than guessed at.

"""

import shlex


def _parses(script):
    try:
        shlex.split(script)
    except ValueError:
        return False
    return True


def match(command):
    return ("'" in command.script and '"' in command.script
            and not _parses(command.script)
            and _parses(command.script.replace("'", '"')))


def get_new_command(command):
    return command.script.replace("'", '"')


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
