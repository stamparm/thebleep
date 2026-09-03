from thebleep.utils import (command_word_index, get_all_executables,
                            raw_script_parts)
from thebleep.specific.sudo import sudo_support
from thebleep.rules.missing_space_before_subcommand import certain


@sudo_support
def match(command):
    start = command_word_index(command.script_parts)
    if start == len(command.script_parts):
        return False
    first_part = command.script_parts[start]
    if "-" not in first_part or first_part in get_all_executables():
        return False
    cmd, rest = first_part.split("-", 1)
    # `ls-la` is `ls -la` and nothing else: a letter or two after the hyphen
    # is a flag cluster, `missing_space_before_known_subcommand` answers it,
    # and this stands aside rather than offering `ls la` beside it. `git-log`
    # and `apt-install` are words, and this rule's own.
    if len(rest) <= 2 and rest.isalpha() and certain(command):
        return False
    return cmd in get_all_executables()


@sudo_support
def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    target = parts[start]
    return command.script.replace(target, target.replace('-', ' ', 1), 1)


priority = 4500
requires_output = False
