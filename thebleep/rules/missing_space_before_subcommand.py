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
            and bool(_get_executable(word))
            # The confident half of this is a rule of its own, and it answers
            # ahead of the spelling correction. See
            # `missing_space_before_known_subcommand`.
            and not certain(command))


@memoize
def _one_edit_away(word):
    """Whether something you could type is a single edit from `word`.

    Programs *and* builtins, which is the set `no_command` guesses from: `exti`
    is one edit from `exit`, and `exit` is not on `PATH`.

    """
    from thebleep import matching

    from thebleep.shells import shell as current_shell

    names = list(get_all_executables())
    known = set(names)
    names.extend(name for name in current_shell.get_builtin_commands()
                 if name not in known)

    best = matching.rank_with_distance(word, names, limit=1)
    return bool(best) and best[0][1] <= 1


def split_at(command):
    """`command` with the space put back, or `None`."""
    executable = _get_executable(command.script_parts[0])
    if not executable:
        return None

    return command.script.replace(executable, u'{} '.format(executable), 1)


def certain(command):
    """Whether the split is a fact rather than a guess.

    Imported by the rule that acts on those, and asked here so that the two do
    not both offer the same suggestion. Kept in this module because it is about
    what a split *is*, and because a rule that imports its sibling's helper is
    easier to follow than two copies of it.

    """
    word = command.script_parts[0]
    executable = _get_executable(word)
    if not executable:
        return False

    remainder = word[len(executable):]

    # A name that is one edit from something installed is a typo of that, and
    # no split competes with it. `apt-gte install x` is `apt-get install x`,
    # not `apt -gte install x` -- a hyphen is not a flag when the word is
    # itself a hyphenated program name, and `apt-get`, `docker-compose` and
    # `pip-tools` are all that shape.
    if _one_edit_away(word):
        return False

    # A flag. `ls-la` is `ls -la` and nothing else -- nobody has ever meant a
    # program called `ls-la`, and no spelling correction competes with it.
    if remainder.startswith('-'):
        return True

    # Or a subcommand the program itself admits to. `git` and `cargo` are the
    # two this tool can ask -- see `replay.DISPATCHERS` -- so `gitstatus` is
    # `git status` for the same reason `git satus` is: git said so.
    #
    # npm, docker and the rest are deliberately absent from that set, for a
    # reason that belongs to replay safety rather than to this. They fall back
    # to the guess, which is what they got before.
    from thebleep import replay

    question = replay.DISPATCHERS.get(executable)
    if question is None:
        return False

    known = replay._subcommands(executable, question)
    return bool(known) and remainder in known


def get_new_command(command):
    return split_at(command)


# After `no_command`, which is at 3000: this is a guess, and where there is a
# name one edit away that is the better guess. The cases where the split is
# *not* a guess have their own rule, in front of `no_command`.
priority = 4000


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
