# -*- encoding: utf-8 -*-

"""`GIT STATUS` -> `git status`. Caps lock, or Shift held a key too long.

`no_command` scores spelling, and to it `GIT` is three substitutions from
`git`: nothing close. But the letters are all right, only their case is
wrong, and a program whose name in lower case is installed is not a guess.

- **Caps lock:** a line with no lower-case letter at all is lowered whole,
  arguments included -- `LS -LA` was typed as `ls -la` with the light on.
- **Shift:** otherwise only the word in the wrong case is lowered:
  `Git status`, `GIT status`, and `git STATUS` when git documents `status`.

A system whose filesystem ignores case runs `GIT` as it is, and then nothing
failed and nothing is asked.

"""

from thebleep.rules.missing_space_before_subcommand import _is_a_command_already
from thebleep.utils import command_word_index, replace_command_word


def _caps_lock(script):
    return script == script.upper() and script != script.lower()


def _lowered(command):
    """The line with its case put right, or `None`."""
    parts = command.script_parts
    start = command_word_index(parts)
    if start == len(parts):
        return None
    word = parts[start]
    if word != word.lower() and not _is_a_command_already(word):
        if not _is_a_command_already(word.lower()):
            return None
        if _caps_lock(command.script):
            return command.script.lower()
        return replace_command_word(command.script, start, word.lower())
    if len(parts) > start + 1 and _is_a_command_already(word):
        second = parts[start + 1]
        if second != second.lower():
            from thebleep import vocabulary

            if second.lower() in (vocabulary.subcommands(word) or ()):
                return replace_command_word(command.script, start + 1,
                                            second.lower())
    return None


def match(command):
    return bool(command.script_parts) and _lowered(command) is not None


def get_new_command(command):
    return _lowered(command)


# Ahead of `no_command`, at 3000: the letters are a fact, only the case was
# wrong.
priority = 2900

# The words themselves are the whole question.
requires_output = False
