import os
import select
import sys
import tty
import termios
import colorama
from pathlib import Path  # noqa: F401
from shutil import which
from .. import const

init_output = colorama.init

# How long to wait for the rest of an escape sequence before deciding that
# the escape key itself was pressed.
ESCAPE_TIMEOUT = 0.05


def _is_incomplete(sequence):
    """Tells whether the terminal still owes us the rest of a key."""
    return sequence in (b'\x1b', b'\x1b[')


def read_key_sequence():
    """Reads a keypress as the characters the terminal sent for it."""
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        # Not a TTY (a pipe, a subprocess or CI), so there's nobody to press
        # a key: abort rather than run something nobody agreed to.
        return '\x03'

    try:
        tty.setraw(fd)
        # Read straight from the descriptor, `sys.stdin` would buffer the
        # rest of an escape sequence out of `select`'s reach.
        sequence = os.read(fd, 6)
        while (_is_incomplete(sequence)
               and select.select([fd], [], [], ESCAPE_TIMEOUT)[0]):
            sequence += os.read(fd, 6 - len(sequence))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return sequence.decode('utf-8', 'replace')


def getch():
    return read_key_sequence()[:1]


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
    """Get a shell command calling the system's generic opener."""
    opener = 'xdg-open' if which('xdg-open') else 'open'
    return opener + ' ' + arg
