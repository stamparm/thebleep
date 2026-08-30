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
import shlex

from thebleep import matching
from thebleep import wrappers
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
    has_output = command.output is not None
    unknown = _unknown_command(command, output_required=has_output)
    if unknown is None:
        substitution = _unknown_in_substitution(
            command, output_required=has_output)
        unknown = substitution[3] if substitution is not None else None
    return bool(unknown and _ranked(unknown[1]))


_COMMAND_SEPARATORS = frozenset(('&&', '||', '|', '|&', ';', '&'))
_ENVIRONMENT_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
_SAFE_COMMAND_NAME = re.compile(r'^[A-Za-z0-9_@%+=:,./-]+$')
_CONTROL_PREFIXES = frozenset(
    ('if', 'then', 'else', 'elif', 'while', 'until', 'do', '!', '(', '{'))
_CONTROL_ENDS = frozenset(('fi', 'done', 'end', ')', '}'))
_POWERSHELL_CONDITIONALS = frozenset(
    ('if', 'elseif', 'while', 'until', 'for', 'foreach', 'switch'))
_POWERSHELL_PREFIXES = frozenset(
    ('else', 'try', 'catch', 'finally', 'function', 'filter', 'process',
     'class', 'param'))


def _is_powershell():
    from thebleep.shells import shell

    return type(shell).__name__ == 'Powershell'


def _compound_parts(command):
    """Command words and separators, including unspaced shell syntax.

    ``Command.script_parts`` deliberately uses each shell's ordinary argument
    splitting. That leaves ``foo&&gti`` as one word, which is fine for most
    rules but hides the second command from this one. Punctuation-aware
    ``shlex`` is used only here, where separators have meaning; quoted text is
    still kept as one argument and malformed input falls back to the shell's
    normal split.
    """
    punctuation = ';&|(){}' if _is_powershell() else ';&|()'
    lexer = shlex.shlex(command.script, posix=True,
                        punctuation_chars=punctuation)
    lexer.whitespace_split = True
    lexer.commenters = ''
    try:
        return list(lexer)
    except ValueError:
        return command.script_parts


def _command_indexes(parts):
    """Indexes of command words in simple compound shell syntax.

    Shell control words are not commands themselves. Keeping the command
    boundary open after ``if`` and ``then`` lets an unknown command inside a
    conditional be corrected without mistaking ``if`` for the failed program.
    Parentheses are handled as subshell boundaries for the same reason.
    The wrapper check comes first: ``env if`` executes a program named ``if``;
    it is not a shell conditional.
    """
    command_start = True
    segment_start = 0
    powershell_condition = False
    condition_depth = 0
    powershell = _is_powershell()
    for index, part in enumerate(parts):
        if powershell_condition:
            if part == '(':
                condition_depth = 1
                powershell_condition = False
            elif part == '{':
                powershell_condition = False
                command_start = True
                segment_start = index
            continue

        if condition_depth:
            if part == '(':
                condition_depth += 1
            elif part == ')':
                condition_depth -= 1
                if condition_depth == 0:
                    command_start = True
                    segment_start = index + 1
            continue

        if part in _COMMAND_SEPARATORS:
            command_start = True
            segment_start = index + 1
        elif part == '}':
            command_start = True
            segment_start = index + 1
        elif command_start:
            command_start_index = segment_start
            while (command_start_index < len(parts)
                   and _ENVIRONMENT_ASSIGNMENT.match(
                       parts[command_start_index])):
                command_start_index += 1
            if command_start_index >= len(parts):
                command_start = False
                continue

            word = parts[command_start_index]
            if word in wrappers.WRAPPERS:
                wrapped = wrappers.wrapped_command_index(
                    parts[command_start_index:])
                if wrapped is None:
                    command_start = False
                    continue
                yield command_start_index + wrapped
                command_start = False
                continue

            if powershell and word in _POWERSHELL_CONDITIONALS:
                powershell_condition = True
                segment_start = command_start_index + 1
                continue
            if powershell and word in _POWERSHELL_PREFIXES:
                segment_start = command_start_index + 1
                continue
            if word in _CONTROL_ENDS:
                command_start = False
                continue
            if word in _CONTROL_PREFIXES:
                segment_start = command_start_index + 1
                continue

            yield command_start_index
            command_start = False


def _unknown_command(command, output_required=True):
    """`(index, word)` for the failed command named by the shell."""
    parts = _compound_parts(command)
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
        for index in _command_indexes(parts):
            if not _is_available_command(parts[index]):
                return index, parts[index]
        return None

    for index in _command_indexes(parts):
        word = parts[index]
        if word in output and not which(word):
            return index, word

    return None


def _is_available_command(word):
    """Whether a command is available as an executable or shell builtin."""
    if which(word):
        return True

    from thebleep.shells import shell

    return word in shell.get_builtin_commands()


def _substitution_ranges(script):
    """Yield the bodies of ``$(...)`` expressions outside single quotes.

    This is intentionally only the small piece of shell structure needed by
    the unknown-command rule. The shell still owns parsing and execution; the
    ranges merely let us inspect a nested command without treating the outer
    command's arguments as executable words.
    """
    for start in range(len(script) - 1):
        if script[start:start + 2] != '$(':
            continue

        quote = None
        escaped = False
        single_quoted = False
        for character in script[:start]:
            if escaped:
                escaped = False
            elif character == '\\' and quote != "'":
                escaped = True
            elif character in ("'", '"'):
                if quote == character:
                    quote = None
                elif quote is None:
                    quote = character
        if quote == "'":
            single_quoted = True
        if single_quoted:
            continue

        depth = 1
        quote = None
        escaped = False
        index = start + 2
        while index < len(script):
            character = script[index]
            if escaped:
                escaped = False
            elif character == '\\' and quote != "'":
                escaped = True
            elif quote:
                if character == quote:
                    quote = None
            elif character in ("'", '"'):
                quote = character
            elif script[index:index + 2] == '$(':
                depth += 1
                index += 1
            elif character == ')':
                depth -= 1
                if depth == 0:
                    yield start + 2, index
                    break
            index += 1


def _unknown_in_substitution(command, output_required=True):
    """Find one unknown command in a command substitution, if unambiguous."""
    found = []
    for start, end in _substitution_ranges(command.script):
        inner = command.update(script=command.script[start:end])
        unknown = _unknown_command(inner, output_required=output_required)
        if unknown is not None:
            found.append((start, end, inner, unknown))

    return found[0] if len(found) == 1 else None


def _replace_substitution_command(script, start, end, command_index, old,
                                  replacement):
    """Replace the identified command word inside one ``$(...)`` body."""
    body = script[start:end]
    if command_index == 0:
        leading = len(body) - len(body.lstrip())
        position = leading + body[leading:].find(old)
        separators = frozenset(';&|(){}')
        if (position < leading or
                (position + len(old) < len(body)
                 and not (body[position + len(old)].isspace()
                          or body[position + len(old)] in separators))):
            return None
        return script[:start + position] + replacement + \
            script[start + position + len(old):]

    corrected = _replace_after_separator(body, old, replacement)
    if corrected is None:
        return None
    return script[:start] + corrected + script[end:]


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


def _replace_after_separator(script, old, replacement):
    """Replace one unquoted ``old`` that starts a separated command.

    A raw occurrence is not enough to identify a command: ``echo gti && gti``
    contains the same word as data and as a program. This small lexer only
    considers occurrences outside quotes, immediately after shell separators;
    when that still leaves more than one choice it returns ``None`` and the
    caller abstains.
    """
    separators = frozenset(';&|({}')
    spans = []
    quote = None
    escaped = False
    index = 0
    while index < len(script):
        character = script[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if character == '\\' and quote != "'":
            escaped = True
            index += 1
            continue
        if character in ("'", '"'):
            if quote == character:
                quote = None
            elif quote is None:
                quote = character
            index += 1
            continue
        if (quote is None and script.startswith(old, index)
                and (index == 0 or script[index - 1].isspace()
                     or script[index - 1] in separators)
                and (index + len(old) == len(script)
                     or script[index + len(old)].isspace()
                     or script[index + len(old)] in separators)):
            before = script[:index].rstrip()
            if before and before[-1] in separators:
                spans.append((index, index + len(old)))
            index += len(old)
            continue
        index += 1

    if len(spans) != 1:
        return None

    start, end = spans[0]
    return script[:start] + replacement + script[end:]


def _used_executables(command):
    """The programs you have actually run, from your history."""
    return {script.split(' ')[0]
            for script in get_valid_history_without_current(command)}


@sudo_support
def get_new_command(command):
    unknown = _unknown_command(command, output_required=False)
    substitution = None
    if unknown is None:
        substitution = _unknown_in_substitution(command, output_required=False)
        if substitution is None:
            return []
        start, end, inner, unknown = substitution

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

    parts = _compound_parts(inner) if substitution else _compound_parts(command)
    ranked = _demote_impossible(ranked, parts[command_index + 1:])

    from thebleep.conf import settings

    from thebleep.shells import shell

    corrected = []
    for name in ranked[:settings.num_close_matches]:
        replacement = (name if _SAFE_COMMAND_NAME.match(name)
                       else shell.quote(name))
        if substitution:
            script = _replace_substitution_command(
                command.script, start, end, command_index,
                old_command, replacement)
        elif command_index == 0:
            script = command.script.replace(old_command, replacement, 1)
        elif command.script.count(old_command) != 1:
            script = _replace_after_separator(command.script, old_command,
                                              replacement)
            if script is None:
                # String replacement cannot identify the right token when the
                # failed command also appears as an argument. Abstain rather
                # than rewrite the wrong occurrence.
                continue
        else:
            script = command.script.replace(old_command, replacement, 1)
        if script is not None and script != command.script:
            corrected.append(script)

    return corrected


priority = 3000

# Inline correction has no stderr by definition. The command finder can still
# identify an uninstalled command from PATH, while the normal failure path
# remains conservative when output exists but does not name a shell error.
requires_output = False
