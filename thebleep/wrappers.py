# -*- encoding: utf-8 -*-

"""Finding the real command behind the words in front of it.

`sudo git chekout`, `env FOO=bar npm sart`, `nice -n 10 cargo buld`,
`nohup ./deploy.sh`, `doas apt instal` -- in every one of these the interesting
command is not the first word, and a rule that asks "is this git?" is told no.

Upstream's answer was a `sudo_support` decorator on twenty-six of the hundred
and seventy rules, which strips a leading `sudo ` and puts it back. It only
knows one wrapper, only in one spelling, and only for the rules that remembered
to ask for it. What is here instead is one model of what a wrapper is, applied
once for every rule: peel the wrapper off, correct what is underneath, and give
the wrapper back with the correction.

Three things decide whether a wrapper may be peeled, and all three fail towards
leaving the command alone:

**The wrapper must be transparent.** `sudo -u www-data git status` runs git;
`sudo -i` runs a login shell, `sudo -e` opens an editor, `sudo -l` lists
privileges and `command -v git` prints a path. Those are not the command
underneath in a hat, so they are refused.

**Its options must be understood.** An option this does not know could be one
that takes a value, and then the value would be mistaken for the command. So an
unrecognised option means no unwrapping rather than a guess -- a correction not
offered costs a keystroke, a wrong one costs more.

**What is peeled off must go back exactly.** The prefix is handed back to the
shell verbatim, cut out of the script the user typed, so nothing is re-quoted
and nothing changes meaning on the way. A wrapper whose words would not survive
that -- one holding a quote or a space -- is left alone, and so is a script with
shell syntax in it, where the first word is not the only command anyway.

"""

import re

# Environment assignments, which both `env` and `sudo` accept in front of the
# command: `env FOO=bar cmd`, `sudo FOO=bar cmd`.
ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')

# `nice -10 cmd` is the old spelling of `nice -n 10 cmd`.
NICENESS = re.compile(r'^-\d+$')

# Shell syntax that makes the first word something other than the whole story:
# with a pipe or a `;` in it the script is several commands, and the wrapper in
# front of the first one says nothing about the rest.
SHELL_SYNTAX = frozenset('|&;<>()`\n\r')


class Wrapper(object):
    """One transparent wrapper, and what its options look like."""

    __slots__ = ('name', 'boolean', 'valued', 'long_valued', 'unsafe',
                 'long_unsafe', 'assignments', 'numeric')

    def __init__(self, name, boolean=(), valued=(), long_valued=(),
                 unsafe=(), long_unsafe=(), assignments=False, numeric=False):
        self.name = name
        # Short options that stand alone, and so may be clustered: `-Eb`.
        self.boolean = frozenset(boolean)
        # Short options that take a value, in the next word or glued on.
        self.valued = frozenset(valued)
        # Long options that take a value, as `--opt value` or `--opt=value`.
        self.long_valued = frozenset(long_valued)
        # Options after which the command is not what runs.
        self.unsafe = frozenset(unsafe)
        self.long_unsafe = frozenset(long_unsafe)
        # Whether `NAME=value` may appear before the command.
        self.assignments = assignments
        # Whether a bare `-10` is an option (nice).
        self.numeric = numeric


# The wrappers this understands. Everything about each one is either in the
# tool's own `--help` or in its manual page; nothing is inferred.
#
# Deliberately absent, and why:
#
#   timeout, watch   take an operand of their own before the command, so the
#                    command is not simply "the first word that is not an
#                    option" and getting it wrong means correcting the duration
#   xargs            builds its own command lines out of what it reads
#   ssh, docker      run the command somewhere else, where a correction worked
#                    out from this machine's PATH and this directory's contents
#                    does not apply
#   strace, ltrace,  transparent, but the output being corrected from is
#   valgrind         theirs rather than the command's
#   time             the same: `time git stauts` prints git's error *and*
#                    time's report, and the rules that pick a name out of a
#                    command's output offered "Command exited with non-zero
#                    status 1" as a branch to check out
WRAPPERS = {
    wrapper.name: wrapper for wrapper in [
        Wrapper(
            'sudo',
            boolean='ABbEHkNnPS',
            valued='CDghpRrTUu',
            long_valued=('close-from', 'chdir', 'group', 'host', 'prompt',
                         'chroot', 'role', 'type', 'command-timeout', 'user',
                         'other-user'),
            # `-i`/`-s` run a shell, `-e` an editor, `-l`/`-v`/`-V`/`-K` run no
            # command at all -- and `-h` is help or host depending on the rest
            # of the line, which is not something to guess at.
            unsafe='eilhKvV',
            long_unsafe=('edit', 'login', 'shell', 'list', 'validate',
                         'version', 'help', 'remove-timestamp'),
            assignments=True),
        Wrapper(
            'doas',
            boolean='nL',
            valued='aCu',
            unsafe='sL'),
        Wrapper(
            'env',
            boolean='iv',
            valued='uC',
            long_valued=('unset', 'chdir', 'block-signal', 'default-signal',
                         'ignore-signal'),
            # `-S` re-splits its argument into the command, `-0` and
            # `--list-signal-handling` print rather than run.
            unsafe='S0',
            long_unsafe=('split-string', 'null', 'list-signal-handling',
                         'help', 'version'),
            assignments=True),
        Wrapper(
            'command',
            boolean='p',
            # `-v` and `-V` print where the command is; they do not run it.
            unsafe='vV'),
        Wrapper('builtin'),
        Wrapper(
            'nice',
            valued='n',
            long_valued=('adjustment',),
            long_unsafe=('help', 'version'),
            numeric=True),
        Wrapper(
            'nohup',
            long_unsafe=('help', 'version')),
        Wrapper(
            'setsid',
            boolean='cfw',
            unsafe='V',
            long_unsafe=('help', 'version')),
        Wrapper(
            'stdbuf',
            valued='ioe',
            long_valued=('input', 'output', 'error'),
            long_unsafe=('help', 'version')),
    ]
}


def _command_starts_at(wrapper, words):
    """Where the wrapped command begins in `words`, or `None` to leave it be.

    `words` is everything after the wrapper's own name.

    """
    index = 0
    while index < len(words):
        word = words[index]

        if word == '--':
            return index + 1 if index + 1 < len(words) else None

        if word.startswith('--'):
            name = word[2:].split('=', 1)[0]
            if name in wrapper.long_unsafe:
                return None
            if '=' in word:
                index += 1
                continue
            if name in wrapper.long_valued:
                index += 2
                continue
            # An option nobody here has heard of. It may take a value, and
            # then the value is not the command -- so nothing is unwrapped.
            return None

        if word.startswith('-') and len(word) > 1:
            if wrapper.numeric and NICENESS.match(word):
                index += 1
                continue
            consumed = _short_options(wrapper, word[1:])
            if consumed is None:
                return None
            index += consumed
            continue

        if wrapper.assignments and ASSIGNMENT.match(word):
            index += 1
            continue

        return index

    # Only the wrapper and its options, with no command after them. `env` alone
    # prints the environment and `nice` alone prints the niceness; neither is
    # the command in a hat.
    return None


def _short_options(wrapper, letters):
    """How many words a cluster of short options takes up, or `None`.

    Returns 1 when the cluster stands on its own, 2 when it ends in an option
    whose value is the next word.

    """
    for position, letter in enumerate(letters):
        if letter in wrapper.unsafe:
            return None
        if letter in wrapper.valued:
            # `-u root` or `-uroot`; either way the rest of the cluster is the
            # value, so nothing after it in this word is another option.
            return 1 if position + 1 < len(letters) else 2
        if letter not in wrapper.boolean:
            return None
    return 1


def _is_literal(word):
    """Whether this word can be handed back to the shell as it stands.

    The prefix is cut out of the script the user typed and put back in front of
    the correction unchanged, so every word in it has to mean the same thing
    written the way it already is. A word that needed quoting does not.

    """
    from shlex import quote

    return bool(word) and quote(word) == word


def _wrapper_words(words):
    """How many of `words` are wrapper, or 0 when the first one is the command.

    Wrappers nest: `sudo nice -n 10 env FOO=bar cargo buld` is three of them in
    front of one command, and each is peeled the same way.

    """
    consumed = 0
    while consumed < len(words):
        wrapper = WRAPPERS.get(words[consumed])
        if wrapper is None:
            break
        starts_at = _command_starts_at(wrapper, words[consumed + 1:])
        if starts_at is None:
            break
        consumed += 1 + starts_at

    return 0 if consumed >= len(words) else consumed


def peel(script, script_parts):
    """Splits `script` into the wrappers in front and the command behind them.

    Returns `(prefix, command)` as two strings, the first ending in whatever
    whitespace separated them, or `(None, None)` when there is nothing to peel
    or peeling would not be safe. Joined back together they are `script`.

    :type script: str
    :type script_parts: [str]
    :rtype: (str, str) | (None, None)

    """
    if len(script_parts) < 2:
        return None, None

    if any(character in script for character in SHELL_SYNTAX):
        return None, None

    consumed = _wrapper_words(script_parts)
    if not consumed:
        return None, None

    prefix_words = script_parts[:consumed]
    if not all(_is_literal(word) for word in prefix_words):
        return None, None

    return _cut(script, prefix_words)


def _cut(script, prefix_words):
    """`script` split in two after `prefix_words`, both halves verbatim.

    Walked through the original text rather than joined back up from the words,
    so that the command keeps its own quoting exactly as it was written: the
    words came out of `shlex`, and `git commit -m "a message"` does not survive
    a round trip through them.

    """
    rest = script.lstrip()
    for word in prefix_words:
        if not rest.startswith(word):
            # The word is not there literally after all, so the split point
            # cannot be found without guessing at it.
            return None, None
        rest = rest[len(word):]
        stripped = rest.lstrip()
        if stripped == rest and rest:
            # No whitespace after the word, so it was not a whole word here.
            return None, None
        rest = stripped

    if not rest:
        return None, None

    return script[:len(script) - len(rest)], rest


def wrapped_app(script_parts):
    """The name of the command behind the wrappers, or `None`.

    For dispatch, which only needs the name and must not care about quoting or
    about how the two halves would be put back together.

    """
    consumed = _wrapper_words(script_parts)
    return script_parts[consumed] if consumed else None
