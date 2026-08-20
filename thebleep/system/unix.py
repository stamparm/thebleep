import os
import sys
from pathlib import Path  # noqa: F401
from .. import const
from .paths import expanduser, writable  # noqa: F401
from .streams import use_utf8


def init_colors():
    """Nothing: a POSIX terminal renders the escape codes itself."""


def init_output():
    """ANSI is native here, so this is only about the encoding.

    Windows also needs a console handler installed before anything is written,
    which is why this exists at all; see `system.win32`.

    """
    use_utf8()


# How long to wait for the rest of an escape sequence before deciding that
# the escape key itself was pressed.
ESCAPE_TIMEOUT = 0.05


def _utf8_length(first):
    """How many bytes the character starting with `first` takes."""
    if first < 0x80:
        return 1
    for length, mask in ((2, 0xE0), (3, 0xF0), (4, 0xF8)):
        if first & mask == (mask << 1) & 0xFF:
            return length

    return 1


def _is_incomplete(sequence):
    """Tells whether the terminal still owes us the rest of a key.

    Two ways a key arrives in pieces: an escape sequence, where the terminal
    sends `\x1b`, then `[`, then the letter; and a character outside ASCII,
    which is two to four bytes of UTF-8.

    """
    if sequence in (b'\x1b', b'\x1b['):
        return True

    return bool(sequence) and len(sequence) < _utf8_length(sequence[0])


def read_key_sequence():
    """Reads a keypress as the characters the terminal sent for it."""
    # The three modules that make a terminal raw are imported here rather than
    # at the top. Only somebody being shown a suggestion and answering it gets
    # this far; `--yes`, `--alias` and every correction that finds nothing
    # never do, and they were all paying to find and open them.
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        # Not a TTY (a pipe, a subprocess or CI), so there's nobody to press
        # a key: abort rather than run something nobody agreed to.
        return '\x03'

    try:
        tty.setraw(fd)
        # One byte at a time, and only more when the key is genuinely
        # unfinished. Reading six at once swallowed whatever came next: `y`
        # followed by Enter arrived as `y\r`, which is not `y`, so answering
        # the replay question the way everybody answers a `[y/N]` prompt was
        # read as "no" -- silently reversing consent on the one prompt that
        # guards re-running your command. A coalesced arrow key was dropped the
        # same way, with no redraw and no beep.
        #
        # What is left in the buffer is not lost: the Enter after the `y` is
        # read by the next prompt, which is where somebody typing `y⏎` wanted
        # it to go anyway.
        #
        # Read straight from the descriptor, `sys.stdin` would buffer the
        # rest of an escape sequence out of `select`'s reach.
        sequence = os.read(fd, 1)
        while (_is_incomplete(sequence)
               and select.select([fd], [], [], ESCAPE_TIMEOUT)[0]):
            sequence += os.read(fd, 1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return sequence.decode('utf-8', 'replace')


def get_key():
    sequence = read_key_sequence()

    if sequence in const.KEY_MAPPING:
        return const.KEY_MAPPING[sequence]
    elif sequence == '\x1b':
        return const.KEY_ESCAPE
    elif sequence == '\x1b[A':
        return const.KEY_UP
    elif sequence == '\x1b[B':
        return const.KEY_DOWN

    return sequence


def open_command(arg):
    """Get a shell command calling the system's generic opener.

    The argument is quoted: it reaches us from the output of whatever command
    just failed, and the result of this goes back to the shell to be evaluated.

    """
    from shutil import which
    from ..shells import shell

    opener = 'xdg-open' if which('xdg-open') else 'open'
    return opener + ' ' + shell.quote(arg)
