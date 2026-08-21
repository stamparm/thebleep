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


# Commands whose first argument has to be a directory. A suggestion that cannot
# possibly succeed is worse than no suggestion, and this is the one case where
# that is knowable without running anything: `cd` was being offered for
# `ca .gitignore`, where `.gitignore` is a file sitting right there.
_WANTS_A_DIRECTORY = frozenset(('cd', 'chdir', 'pushd', 'rmdir'))


def _cannot_work(name, arguments):
    """Whether `name` is certain to fail on the arguments already typed.

    Only certainty counts. A path that does not exist is not evidence -- it may
    be a typo of its own, or relative to somewhere else -- so this says nothing
    about it. A path that exists and is not a directory, handed to `cd`, is an
    error message with no way round it.

    """
    import os

    if name not in _WANTS_A_DIRECTORY:
        return False

    for argument in arguments:
        if argument.startswith('-'):
            continue
        return os.path.exists(argument) and not os.path.isdir(argument)

    return False


def _demote_impossible(ranked, arguments):
    """The same names, with the ones that cannot run moved to the back.

    Moved rather than dropped: this knows that `cd somefile` fails, not what you
    were going to do about it, and the name is still one keystroke from what you
    typed.

    """
    possible = [name for name in ranked if not _cannot_work(name, arguments)]
    impossible = [name for name in ranked if _cannot_work(name, arguments)]
    return possible + impossible


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

    # History breaks a tie and nothing more. Among candidates the metric cannot
    # choose between, prefer the one you have used; anything worse stays where
    # it is.
    #
    # "Equally good" used to mean the same edit *distance* and nothing else, so
    # every one-edit candidate counted as a tie and history reordered them
    # freely:
    #
    #     $ ca .gitignore
    #     $ bleep
    #     cd .gitignore            <- and `cat .gitignore` second
    #
    # `cat` is `ca` with the last key missed, which is the commonest slip there
    # is; `cd` is `a` mistyped as `d`, two keys away and hit with a different
    # finger. The metric knew that and had already put `cat` first -- but `cd`
    # was one edit away too, which was all it took to qualify, and `cd` is in
    # everybody's history because it is the most-typed command there is. So the
    # tie-break promoted the worse answer, every time, for anyone.
    #
    # `plausible_slips` asks for both: as close as the closest, and explainable
    # as one slip. `got` still gives you `git` over `go` -- `o` and `i` are
    # neighbours, so both are real explanations and your history is the right
    # thing to choose between them.
    equal = matching.plausible_slips(old_command, scored)
    if len(equal) > 1:
        familiar = [name for name in equal if name in used]
        if familiar:
            ranked = familiar + [name for name in ranked
                                 if name not in familiar]

    ranked = _demote_impossible(ranked, command.script_parts[1:])

    from thebleep.conf import settings

    return [command.script.replace(old_command, name, 1)
            for name in ranked[:settings.num_close_matches]]


priority = 3000
