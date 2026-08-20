# -*- encoding: utf-8 -*-

# Redirects cs to cd when there is a typo
# Due to the proximity of the keys - d and s - this seems like a common typo
# ~ > cs /etc/
# cs: command not found
# ~ > bleep
# cd /etc/ [enter/↑/↓/ctrl+c]
# /etc >


def match(command):
    if command.script_parts[0] == 'cs':
        return True


def get_new_command(command):
    return 'cd' + ''.join(command.script[2:])


priority = 900


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
