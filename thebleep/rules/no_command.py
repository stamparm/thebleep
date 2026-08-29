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

For a compound command it follows simple shell separators and fixes the
command word named by the shell, such as `cd project && gti status`.

"""

import re

from thebleep import matching
from thebleep.utils import get_all_executables, \
    get_valid_history_without_current, memoize, replace_argument, which
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
    unknown = _unknown_command(command)
    return bool(unknown and _ranked(unknown[1]))


_COMMAND_SEPARATORS = frozenset(('&&', '||', '|', '|&', ';', '&'))
_ENVIRONMENT_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
_SAFE_COMMAND_NAME = re.compile(r'^[A-Za-z0-9_@%+=:,./-]+$')


def _command_indexes(parts):
    """Indexes of command words in simple compound shell syntax."""
    command_start = True
    for index, part in enumerate(parts):
        if part in _COMMAND_SEPARATORS:
            command_start = True
        elif command_start:
            if _ENVIRONMENT_ASSIGNMENT.match(part):
                continue
            yield index
            command_start = False


def _unknown_command(command, output_required=True):
    """`(index, word)` for the failed command named by the shell."""
    output = command.output or ''
    if not ('not found' in output
            # fish says `fish: Unknown command: gerp` and never the words
            # "not found", so every unknown command in fish -- the
            # commonest way a command fails in a shell this supports --
            # went uncorrected.
            or 'unknown command' in output.lower()
            or 'is not recognized as' in output):
        if output_required:
            return None
        index = next(iter(_command_indexes(command.script_parts)), None)
        return ((index, command.script_parts[index])
                if index is not None else None)

    for index in _command_indexes(command.script_parts):
        word = command.script_parts[index]
        if word in output and not which(word):
            return index, word

    return None


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
    unknown = _unknown_command(command, output_required=False)
    if unknown is None:
        return []

    command_index, old_command = unknown

    scored = _ranked(old_command)
    if not scored:
        return []

    # Nothing here is one plausible slip from what was typed. Similar is not
    # the same as mistyped: on a machine without `cargo`, `cargo` is two
    # non-neighbouring substitutions from `xargs`, and offering `xargs buld`
    # for `cargo buld` invents a command nobody meant. Every correction this
    # rule has ever been right about was a dropped, doubled or transposed key,
    # or a neighbouring one -- which is exactly what `plausible` asks for --
    # so that is the floor, and below it the honest answer is silence.
    if not matching.plausible_slips(old_command, scored):
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
    # `plausible_slips`, the floor above, is also the tie set: as close as the
    # closest and explainable as one slip. `got` still gives you `git` over
    # `go` -- `o` and `i` are neighbours, so both are real explanations and
    # your history is the right thing to choose between them.
    equal = matching.plausible_slips(old_command, scored)
    if len(equal) > 1:
        familiar = [name for name in equal if name in used]
        if familiar:
            ranked = familiar + [name for name in ranked
                                 if name not in familiar]

    ranked = _demote_impossible(ranked, command.script_parts[command_index + 1:])

    from thebleep.conf import settings

    from thebleep.shells import shell

    corrected = []
    for name in ranked[:settings.num_close_matches]:
        replacement = (name if _SAFE_COMMAND_NAME.match(name)
                       else shell.quote(name))
        if command_index == 0:
            script = command.script.replace(old_command, replacement, 1)
        elif command.script.count(' ' + old_command) != 1:
            # String replacement cannot identify the right token when the
            # failed command also appears as an argument. Abstain rather than
            # rewrite the wrong occurrence.
            continue
        else:
            script = replace_argument(command.script, old_command, replacement)
        if script != command.script:
            corrected.append(script)

    return corrected


priority = 3000
