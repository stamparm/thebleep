# -*- encoding: utf-8 -*-

# Redirects cs to cd when there is a typo
# Due to the proximity of the keys - d and s - this seems like a common typo
# ~ > cs /etc/
# cs: command not found
# ~ > bleep
# cd /etc/ [enter/↑/↓/ctrl+c]
# /etc >

from thebleep.utils import command_word_index, raw_script_parts


def match(command):
    start = command_word_index(command.script_parts)
    if start < len(command.script_parts) \
            and command.script_parts[start] == 'cs':
        return True


def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    return command.script.replace(parts[start], 'cd', 1)


priority = 900


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
