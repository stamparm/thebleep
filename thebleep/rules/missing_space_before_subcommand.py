# -*- encoding: utf-8 -*-

"""`gitstatus` -> `git status`. A space that did not get typed.

A guess, and one with a failure mode worth naming: it fires whenever the first
word is not runnable but *some prefix of it* is. On a machine missing a command
that begins with the name of one it has, that is nonsense offered with a
straight face:

    $ sudo apt-get updte              # in a container with no sudo
    sudo: command not found
    $ bleep
    su do apt-get updte               <- `su do` is not a command either

`su` is a prefix of `sudo`, so the rule split a real command name it had simply
never heard of. `git k` for `gitk`, `pip x` for `pipx` and `comm and` for
`command` are the same slip -- and the last of those is why builtins were added
to `_is_a_command_already`.

Two guards, and they are the reason this is worth keeping rather than deleting:

- **the remainder has to be two characters or more.** `gitk` -> `git k` and
  `pipx` -> `pip x` are the whole of the one-character case, and neither has
  ever been what somebody meant.
- **a name The Bleep already knows is never split.** `sudo`, `doas`, `env`,
  `nice` and the rest are commands this tool has a model of; a machine without
  one is missing a command, it has not gained a typo.

What survives is what the rule is for: a subcommand (`gitstatus`, `npminstall`)
or a flag (`ls-la`) that lost its space.

"""

from thebleep.shells import shell
from thebleep.utils import get_all_executables, memoize

# The shortest remainder worth splitting off. One character is `gitk`, `pipx`,
# `lsd`, `duf` -- real programs, every one of them.
SHORTEST_REMAINDER = 2


@memoize
def _executables():
    """Everything runnable, as a set.

    This rule has no app name and no output marker, so it is consulted for
    every failed command there is -- and it asked `word in
    get_all_executables()`, which is a scan of a list of some thousands of
    names, before scanning the same list again to find one the word starts
    with.

    """
    return set(get_all_executables())


@memoize
def _known_name(word):
    """Whether this is a command The Bleep itself has a model of.

    The wrappers, which is where `sudo` is. Not installed is not the same as
    misspelled, and for these names this tool is in a position to know.

    """
    from thebleep.wrappers import WRAPPERS

    return word in WRAPPERS


@memoize
def _get_executable(script_part):
    for executable in get_all_executables():
        if len(executable) <= 1 or not script_part.startswith(executable):
            continue
        if len(script_part) - len(executable) < SHORTEST_REMAINDER:
            continue
        return executable


def _is_a_command_already(word):
    """Whether the shell would find something to run under this name.

    Both halves matter. `get_all_executables` is what is on `PATH` plus your
    aliases, and it does not include the shell's own builtins -- so `command`,
    `time` and `builtin` looked like words nobody could run, and this rule
    helpfully offered to break `command git status` into `comm and git status`.

    """
    return (word in _executables()
            or word in shell.get_builtin_commands())


def match(command):
    if not command.script_parts:
        return False

    word = command.script_parts[0]
    return (not _is_a_command_already(word)
            and not _known_name(word)
            and bool(_get_executable(word)))


def get_new_command(command):
    executable = _get_executable(command.script_parts[0])
    return command.script.replace(executable, u'{} '.format(executable), 1)


priority = 4000


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
