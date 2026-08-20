# -*- encoding: utf-8 -*-

CEDILLA = u"ç"


def match(command):
    return command.script.endswith(CEDILLA)


def get_new_command(command):
    return command.script[:-1]


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
