# -*- encoding: utf-8 -*-

"""`whomi` -> `whoami`. No such program, so guess which one was meant.

The busiest path in the tool -- an unrecognised command is the commonest way a
command fails -- and the only one with no tool to ask, so the answer is a pure
guess. It is also the one that was least thought about, and it showed:

    $ whomi
    Command 'whomi' not found
    $ bleep
    which

Two faults, both fixed here.

*Your history was an override rather than a hint.* The closest name from your
shell history was put first with no comparison against the best answer
available. `whoami` is one edit from `whomi`; `which` is three, and qualified
only because the old cutoff sat at 0.6. `which` won because it was in the
history -- put there, as it happens, by somebody running `which bleep` while
debugging this very tool.

The idea behind it is sound and worth keeping. On a machine with several
thousand executables, pure similarity will happily offer `tic`, `grotty` or
`acorn` -- programs nobody has ever run. History is a decent proxy for "commands
this person actually uses". So it now breaks a tie rather than deciding: a name
you have used wins when it is *as good* a match, and never when it is worse.

*The metric could not see a transposition.* That was `difflib`'s doing and is
now `thebleep.matching`'s job; see the module for why `gti` used to suggest
`tic`.

"""

from thebleep import matching
from thebleep.utils import get_all_executables, \
    get_valid_history_without_current, memoize, which
from thebleep.specific.sudo import sudo_support


@memoize
def _ranked(word):
    """`(name, distance)` for every plausible candidate, best first.

    Memoized, because `match` and `get_new_command` both want it and this is
    the busiest path in the tool: an unknown command is the commonest way a
    command fails, and the scan is a Damerau-Levenshtein distance against every
    name on `PATH` -- around seven thousand of them on this machine, at 25ms a
    pass. It was done twice per correction, and then a third partial pass
    recomputed the distances the second one had already worked out.

    One process is one correction, so a cache that lives as long as the process
    is exactly the right lifetime.

    """
    return matching.rank_with_distance(word, _candidates())


def match(command):
    return (not which(command.script_parts[0])
            and ('not found' in command.output
                 # fish says `fish: Unknown command: gerp` and never the words
                 # "not found", so every unknown command in fish -- the
                 # commonest way a command fails, in a shell this supports --
                 # went uncorrected.
                 or 'unknown command' in command.output.lower()
                 or 'is not recognized as' in command.output)
            and bool(_ranked(command.script_parts[0])))


def _candidates():
    """Everything that could have been meant: programs *and* shell builtins.

    Only `PATH` was searched, so `exit`, `cd`, `alias` and the other fifty-odd
    builtins were not candidates at all -- `exti` could not reach `exit` however
    obvious the slip. They are commands you can type, so they belong in the
    list.

    """
    from thebleep.shells import shell

    names = list(get_all_executables())
    known = set(names)
    return names + [name for name in shell.get_builtin_commands()
                    if name not in known]


def _used_executables(command):
    """The programs you have actually run, from your history."""
    return {script.split(' ')[0]
            for script in get_valid_history_without_current(command)}


@sudo_support
def get_new_command(command):
    old_command = command.script_parts[0]

    scored = _ranked(old_command)
    if not scored:
        return []

    ranked = [name for name, _ in scored]
    used = _used_executables(command)

    # History breaks a tie and nothing more. `rank_with_distance` has already
    # put the candidates in order, so anything sharing the best distance is
    # equally good by the metric -- and among equals, prefer the one you have
    # used. Anything worse stays where it is.
    best = scored[0][1]
    equal = [name for name, edits in scored if edits == best]
    if len(equal) > 1:
        familiar = [name for name in equal if name in used]
        if familiar:
            ranked = familiar + [name for name in ranked
                                 if name not in familiar]

    from thebleep.conf import settings

    return [command.script.replace(old_command, name, 1)
            for name in ranked[:settings.num_close_matches]]


priority = 3000
