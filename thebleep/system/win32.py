import msvcrt
from pathlib import Path  # noqa: F401
from .. import const
from .paths import expanduser, writable  # noqa: F401
from .streams import use_utf8


def init_output():
    """What has to be true of the streams before anything writes to them.

    `win_unicode_console.enable()` used to be here too. CPython has spoken
    Unicode to the Windows console natively since 3.6 (PEP 528 and PEP 529),
    the package has been unmaintained since 2018, and this requires 3.9.

    """
    use_utf8()


def init_colors():
    """Makes the console render the escape codes, the first time one is used.

    This was part of `init_output` and so ran on every invocation. colorama
    reaches the console through `ctypes`, and a `.pyd` is the most expensive
    kind of module there is to import on Windows -- the scanner reads a DLL
    before it is mapped. Most invocations emit no colour at all: `--alias` runs
    at every shell startup and writes a shell function, a correction with
    `--yes` writes one line of shell, and colour is switched off outright when
    the stream is not a console or the user asked for none. So it happens where
    the first escape code is actually produced instead, in `logs.color`.

    `use_utf8` still runs first, in `init_output`, because colorama replaces
    the streams with proxies that have no encoding of their own to set.

    """
    if init_colors.done:
        return
    init_colors.done = True

    import colorama

    colorama.init()


init_colors.done = False


def get_key():
    """The next keypress, the way the POSIX reader reports it.

    `msvcrt.getwch` raises `KeyboardInterrupt` on Ctrl+C -- it is documented to,
    and it is the only reader here that does -- so Ctrl+C at the suggestion list
    or at the replay question came out as a traceback on Windows. `main` catches
    `BrokenPipeError` and nothing else. The POSIX reader hands back the sentinel
    and `ui.read_actions` turns it into an abort; this now does the same, so
    Ctrl+C means the same thing on both.

    """
    prefixed = False
    try:
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):  # arrow or function key prefix?
            prefixed = True
            ch = msvcrt.getwch()  # second call returns the actual key code
    except KeyboardInterrupt:
        return const.KEY_CTRL_C

    if ch in const.KEY_MAPPING:
        return const.KEY_MAPPING[ch]
    if ch == '\x1b':
        return const.KEY_ESCAPE
    # Only after the prefix: a plain capital H or P is a letter, not an arrow.
    if prefixed and ch == 'H':
        return const.KEY_UP
    if prefixed and ch == 'P':
        return const.KEY_DOWN

    return ch


def open_command(arg):
    """Get a shell command calling the system's generic opener.

    The argument is quoted: it reaches us from the output of whatever command
    just failed, and the result of this goes back to the shell to be evaluated.

    """
    from ..shells import shell

    return 'cmd /c start ' + shell.quote(arg)
