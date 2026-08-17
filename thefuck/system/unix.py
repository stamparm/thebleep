import sys
import tty
import termios
import colorama
from pathlib import Path  # noqa: F401
from shutil import which
from .. import const

init_output = colorama.init


def getch():
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        # Not a TTY (e.g. piped input, subprocess capture, CI).
        # Return newline to auto-select the first suggestion.
        return '\n'
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def get_key():
    ch = getch()

    if ch in const.KEY_MAPPING:
        return const.KEY_MAPPING[ch]
    elif ch == '\x1b':
        next_ch = getch()
        if next_ch == '[':
            last_ch = getch()

            if last_ch == 'A':
                return const.KEY_UP
            elif last_ch == 'B':
                return const.KEY_DOWN

    return ch


def open_command(arg):
    """Get a shell command calling the system's generic opener."""
    opener = 'xdg-open' if which('xdg-open') else 'open'
    return opener + ' ' + arg
