# -*- encoding: utf-8 -*-

"""`ls - la` -> `ls -la`. The space went in after the dash.

A bare `-` is a real argument -- standard input to `cat`, the previous
directory to `cd`, the previous branch to `git checkout` -- so this is never
said before the line runs, and not after it either unless the program itself
complained about the pieces: the `-` or the word after it named as an
operand it could not use.

    $ ls - la
    ls: cannot access '-': No such file or directory
    ls: cannot access 'la': No such file or directory

    $ git log - p
    fatal: ambiguous argument 'p': unknown revision or path not in the
    working tree.

The word after the dash has to look like what follows a dash: up to four
letters or digits. Every such pair on the line is joined.

"""

import re

from thebleep.utils import raw_script_parts

_FLAG = re.compile(r'^[A-Za-z0-9]{1,4}$')


def _named(word, output):
    """Whether `output` complains about `word` as an operand: quoted
    (`'p'`, `"-"`), or at the start of a message (`grep: r: No such`)."""
    word = re.escape(word)
    return bool(re.search(u'[\'"‘“]{0}[\'"’”]|: {0}: '
                          .format(word), output))


def _pairs(parts):
    return [index for index in range(1, len(parts) - 1)
            if parts[index] == '-' and _FLAG.match(parts[index + 1])]


def match(command):
    if not command.output:
        return False
    parts = raw_script_parts(command.script)
    pairs = _pairs(parts)
    return bool(pairs) and any(
        _named('-', command.output) or _named(parts[index + 1],
                                              command.output)
        for index in pairs)


def get_new_command(command):
    parts = raw_script_parts(command.script)
    joined = set(_pairs(parts))
    words = []
    skip = False
    for index, part in enumerate(parts):
        if skip:
            skip = False
            continue
        if index in joined:
            words.append('-' + parts[index + 1])
            skip = True
        else:
            words.append(part)
    return ' '.join(words)


# Ahead of the rules that read the same complaint some other way -- `grep -r`
# for `grep: .: Is a directory`, a branch for git's unmatched pathspec.
priority = 900

# The program's own complaint is the evidence, so this reads the output.
requires_output = True
