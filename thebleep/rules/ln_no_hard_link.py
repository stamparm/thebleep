# -*- coding: utf-8 -*-
"""Suggest creating symbolic link if hard link is not allowed.

Example:
> ln barDir barLink
ln: ‘barDir’: hard link not allowed for directory

--> ln -s barDir barLink
"""

from thebleep.specific.sudo import sudo_support
from thebleep.utils import command_word_index, raw_script_parts


@sudo_support
def match(command):
    # `in`, not `endswith`: the output arrives with its trailing newline from
    # a replay and without it from a pane, and the rule was dead after a
    # replay.
    return ("hard link not allowed for directory" in command.output and
            command_word_index(command.script_parts)
            < len(command.script_parts) and
            command.script_parts[command_word_index(command.script_parts)]
            == 'ln')


@sudo_support
def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    target = parts[start]
    return command.script.replace(target, 'ln -s', 1)
