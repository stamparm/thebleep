# -*- encoding: utf-8 -*-

"""`ls --sort=nmae` -> `ls --sort=name`. The tool printed the answers.

    $ ls -l --sort=nmae
    ls: invalid argument 'nmae' for '--sort'
    Valid arguments are:
      - 'none'
      - 'time'
      - 'size'
      - 'extension'
      - 'version'
      - 'width'
    Try 'ls --help' for more information.

Which is as clear as an error message gets: the value it did not understand and
every value it does, in one place. What The Bleep did with it was answer
`ls --help` -- `long_form_help` matching that last line, throwing the rest of
the command away, and offering a help screen as a correction.

This is the same shape as the framework rules (`clap_suggestion` and friends):
the list comes from the program, so it is ordered rather than filtered -- see
`matching.order` for why those two are different.

`ambiguous argument` as well as `invalid argument`, because a prefix that
matches several values gets the identical listing.

The wording belongs to gnulib's `argmatch`, so it is not an `ls` feature: `du
--time`, `ls --format`, `ls --quoting-style`, `df --output` and a good many
others print exactly this. That is why the rule keys on the message rather than
on a program name. Captured from GNU coreutils 9.4, in both the UTF-8 and the C
locale -- the quotes are typographic in one and plain in the other.

"""

import re
from thebleep import matching
from thebleep.utils import memoize, replace_value

# Either quote style: gnulib prints `'x'` under LC_ALL=C and `‘x’` otherwise.
_Q = u'[\'‘’]'

REJECTED = re.compile(
    u'(?:invalid|ambiguous) argument {q}([^\'‘’]*){q}'
    u' for {q}(--?[^\'‘’]*){q}'.format(q=_Q))

# `Valid arguments are:` and then indented lines of quoted names, several to a
# line where they are synonyms: `  - 'atime', 'access', 'use'`.
LISTING = u'Valid arguments are:'
QUOTED = re.compile(u'{q}([^\'‘’]+){q}'.format(q=_Q))


@memoize
def _rejected_and_valid(output):
    """`(what was rejected, what would be accepted)`, or `None`.

    Memoized on the output, because `match` and `get_new_command` both want it.

    """
    found = REJECTED.search(output)
    if not found:
        return None

    lines = output.split('\n')
    for index, line in enumerate(lines):
        if LISTING in line:
            break
    else:
        return None

    valid = []
    for line in lines[index + 1:]:
        if not line.startswith((' ', '\t')):
            # The listing is indented; the `Try 'ls --help'` line is not.
            break
        valid.extend(QUOTED.findall(line))

    if not valid:
        return None

    return found.group(1), valid


def match(command):
    return _rejected_and_valid(command.output) is not None


def get_new_command(command):
    rejected, valid = _rejected_and_valid(command.output)

    # `replace_value` because the value can be glued to its option with an
    # `=`, which `replace_argument` cannot see. It quotes, too: these names came
    # out of the program's own output.
    return [replace_value(command.script, rejected, name)
            for name in matching.order(rejected, valid, limit=3)]


# Ahead of `long_form_help`, which is at 5000 and answers this output with
# `ls --help` -- a help screen dressed as a correction, with the rest of the
# command discarded.
priority = 1500
