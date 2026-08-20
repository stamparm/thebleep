# -*- encoding: utf-8 -*-

"""`git log README.md --oneline` -> the flag goes before the filename.

Four ways this raised, all of them on the way to a suggestion nobody would see
-- `Rule.get_corrected_commands` catches the exception, so the only symptom was
the rule quietly never firing:

- `match` was called again inside `get_new_command` and its result
  dereferenced. `git_support` rewrites the command on the way in, so the second
  call was not looking at the same thing as the first, and `None.group(1)` is
  what happens when it disagrees.
- `command_parts.index(bad_flag)` on a flag that git named but that is not a
  word of the command -- `--oneline=x` reported as `--oneline` -- raises
  `ValueError`.
- `filename_index` was only assigned inside the loop, so a command whose words
  before the flag are all flags raised `UnboundLocalError`.
- an empty name in the message left `command_parts[index][0]` indexing an
  empty string.

Parsed once, in `match`, and carried across. Anything that does not line up is
a rule that stands aside rather than one that raises.

Wordings captured from git 2.43.

"""

import re
from thebleep.specific.git import git_support

error_pattern = "fatal: bad flag '(.*?)' used after filename"
error_pattern2 = "fatal: option '(.*?)' must come before non-option arguments"


def _swap(command):
    """`(bad_flag_index, filename_index)`, or `None`.

    The whole question, answered once. `match` needs to know that there is an
    answer and `get_new_command` needs the answer itself, and asking twice was
    asking two different questions.

    """
    found = (re.search(error_pattern, command.output)
             or re.search(error_pattern2, command.output))
    if not found:
        return None

    parts = command.script_parts
    bad_flag = found.group(1)
    if bad_flag not in parts:
        # git named something that is not a word of this command: a flag it
        # normalised, or one that arrived glued to its value.
        return None

    flag_index = parts.index(bad_flag)
    for index in reversed(range(flag_index)):
        word = parts[index]
        if word and not word.startswith('-'):
            return flag_index, index

    # Nothing but flags in front of it, so there is no filename to swap with.
    return None


@git_support
def match(command):
    return _swap(command) is not None


@git_support
def get_new_command(command):
    swap = _swap(command)
    if swap is None:
        return []

    flag_index, filename_index = swap
    command_parts = command.script_parts[:]
    command_parts[flag_index], command_parts[filename_index] = \
        command_parts[filename_index], command_parts[flag_index]

    return u' '.join(command_parts)
