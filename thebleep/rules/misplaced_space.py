# -*- encoding: utf-8 -*-

"""`sud osu` -> `sudo su`. The space did not go missing -- it went to the
wrong place.

`no_command` only ever touches the first word. It found `sudo` one edit from
`sud`, glued it back in, and never looked at `osu`:

    $ sud osu
    Command 'sud' not found
    $ bleep
    sudo osu                 <- and `osu` is not a command either

Two typos, not one, and the second was invisible to a rule that scores each
word alone. `su`, sitting one character from the space, was the shell's own
first suggestion once `osu` was tried on its own -- the evidence was right
there, just split wrong.

This is not a guess in the sense `no_command` is. There, "sudo" was the best
of several edits away and might have been wrong. Here, sliding the space
along `sudosu` and landing on `sudo` + `su` explains both halves completely --
nothing is left over, and nothing was invented. That is the same shape of
certainty as `missing_space_before_known_subcommand`, so it answers ahead of
`no_command` too.

Only the first two words are ever considered. A third `sud osu foo` slip is
still two words wrong, and everything after them rides along untouched.

"""

from thebleep.rules.missing_space_before_subcommand import _is_a_command_already
from thebleep.utils import which

# Below this, a split is one coincidence away from two real but unrelated
# one-letter names -- `s` is not evidence of anything. Mirrors the
# `SHORTEST_REMAINDER` guard next door.
SHORTEST_HALF = 2


def _splits(merged):
    """`(first, second)` for every way to cut `merged` in two, both halves
    long enough to mean something."""
    for i in range(SHORTEST_HALF, len(merged) - SHORTEST_HALF + 1):
        yield merged[:i], merged[i:]


def _respaced(command):
    """The two known names hiding in the first two words, or `None`.

    `None` when there is not exactly one way to explain both words at once --
    zero is no fix, more than one is not the certainty this rule promises.

    """
    parts = command.script_parts
    if len(parts) < 2:
        return None

    merged = parts[0] + parts[1]
    found = [(a, b) for a, b in _splits(merged)
             if _is_a_command_already(a) and _is_a_command_already(b)]

    if len(found) != 1:
        return None

    return found[0]


def match(command):
    return (bool(command.script_parts)
            and not which(command.script_parts[0])
            and not _is_a_command_already(command.script_parts[0])
            and bool(_respaced(command)))


def get_new_command(command):
    parts = command.script_parts
    first, second = _respaced(command)

    old = u'{} {}'.format(parts[0], parts[1])
    if old not in command.script:
        return []

    return [command.script.replace(old, u'{} {}'.format(first, second), 1)]


# Ahead of `no_command`, at 3000, for the same reason
# `missing_space_before_known_subcommand` is: a fact beats a guess.
priority = 2900

# The two words themselves are the whole question.
requires_output = False
