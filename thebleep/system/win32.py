import msvcrt
from pathlib import Path  # noqa: F401
from .. import const
from .paths import expanduser, writable  # noqa: F401
from .streams import use_utf8


def init_output():
    import colorama

    # Before colorama, which replaces the streams with proxies that have no
    # encoding of their own to set.
    #
    # `win_unicode_console.enable()` used to be here too. CPython has spoken
    # Unicode to the Windows console natively since 3.6 (PEP 528 and PEP 529),
    # the package has been unmaintained since 2018, and this requires 3.9.
    use_utf8()
    colorama.init()


def get_key():
    ch = msvcrt.getwch()
    if ch in ('\x00', '\xe0'):  # arrow or function key prefix?
        ch = msvcrt.getwch()  # second call returns the actual key code

    if ch in const.KEY_MAPPING:
        return const.KEY_MAPPING[ch]
    if ch == '\x1b':
        return const.KEY_ESCAPE
    if ch == 'H':
        return const.KEY_UP
    if ch == 'P':
        return const.KEY_DOWN

    return ch


def open_command(arg):
    """Get a shell command calling the system's generic opener.

    The argument is quoted: it reaches us from the output of whatever command
    just failed, and the result of this goes back to the shell to be evaluated.

    """
    from ..shells import shell

    return 'cmd /c start ' + shell.quote(arg)


# `Path.expanduser = ...` used to be here, replacing pathlib's own with one
# built on `os.path.expanduser`, for http://bugs.python.org/issue19776 -- which
# was fixed in Python 3.5, four releases before the oldest one this supports.
#
# It was also a monkeypatch of the standard library for the whole process,
# imposed on every other package in the interpreter, and it changed the
# behaviour: pathlib raises RuntimeError when it cannot work out where home is,
# and `os.path.expanduser` quietly hands back the `~` unexpanded, which is a
# path that does not exist and is much harder to explain.
