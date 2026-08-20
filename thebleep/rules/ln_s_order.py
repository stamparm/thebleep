# -*- encoding: utf-8 -*-

"""`ln -s newlink existing` -> the arguments the other way round.

`ln -s A B` makes `B` a link to `A`, and the slip this is for is typing them
backwards -- which ln reports as `File exists`, because the name it was asked to
create is the one that is already there.

What it used to do was take the *first* argument that exists on disk and move it
to the end. When both exist, that is the source, and moving the source to the
end asks ln to create a link where the source was:

    $ ln -s /etc/hostname /tmp/l1        # /tmp/l1 is already a link
    ln: failed to create symbolic link '/tmp/l1': File exists
    $ bleep
    ln -s /tmp/l1 /etc/hostname          <- a link on top of /etc/hostname

Which is a destructive suggestion for a command that was written correctly and
only needed `-f`. Both arguments existing is not the case this rule is for; it
is the case where nothing needs reordering.

So: exactly two operands, the second one there (which is what `File exists` is
about) and the first one *not* there. That is the reversed command and nothing
else. Message wording captured from GNU coreutils 9.x.

"""

import os
import re
from thebleep.specific.sudo import sudo_support

# `ln: failed to create symbolic link 'x': File exists` -- the name ln was
# asked to create, which is the second operand.
FAILED = re.compile(r"failed to create symbolic link '([^']*)': File exists")

FLAGS = {'-s', '--symbolic', '-f', '--force', '-n', '--no-dereference',
         '-v', '--verbose', '-r', '--relative', '-T', '--no-target-directory'}


def _operands(script_parts):
    """The two names, in the order they were typed, or `None`.

    Anything that is not `ln` and not a flag this knows. An unrecognised option
    could be one that takes a value, and then the value would be counted as an
    operand -- so anything unrecognised means standing aside, the same way
    `wrappers` refuses a wrapper option it does not know.

    """
    names = []
    for part in script_parts[1:]:
        if part in FLAGS:
            continue
        if part.startswith('-'):
            return None
        names.append(part)

    return names if len(names) == 2 else None


def _reversed_pair(command):
    """`(source, destination)` as typed, when the pair really is reversed."""
    names = _operands(command.script_parts)
    if names is None:
        return None

    source, destination = names

    # The name ln could not create, when it said which. It is the second
    # operand; if the message names something else, this is not that failure.
    named = FAILED.search(command.output)
    if named and named.group(1) != destination:
        return None

    # The second exists -- that is what `File exists` means -- and the first
    # does not, which is what makes this the reversed command rather than one
    # that was written correctly and wants `-f`.
    if not os.path.exists(destination) or os.path.exists(source):
        return None

    return source, destination


@sudo_support
def match(command):
    return (command.script_parts[:1] == ['ln']
            and bool({'-s', '--symbolic'}.intersection(command.script_parts))
            and 'File exists' in command.output
            and _reversed_pair(command) is not None)


@sudo_support
def get_new_command(command):
    pair = _reversed_pair(command)
    if pair is None:
        return []

    source, destination = pair
    parts = command.script_parts[:]
    # Swapped in place, so the flags stay exactly where they were written.
    first, second = parts.index(source), parts.index(destination)
    parts[first], parts[second] = parts[second], parts[first]
    return ' '.join(parts)
