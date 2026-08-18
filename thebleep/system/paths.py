"""Expanding `~` without falling over when there is no home to expand it to.

`Path.expanduser()` raises `RuntimeError: Could not determine home directory.`
when it cannot work out where home is. On POSIX the password database answers
even with `HOME` unset, so it effectively never happens; on Windows there is no
such fallback, and no `USERPROFILE` and no `HOME` means the exception -- a
service account, a stripped container, or a test that cleared the environment.

Ten call sites asked pathlib that question, and every one of them would take the
whole run down with it, including the two on the path of every correction. This
used to be hidden by a monkeypatch of `pathlib.Path.expanduser` installed for
Windows, which was worth removing -- patching the standard library for every
other package in the interpreter is not a way to answer a question about our own
paths -- but removing it without answering the question here was the mistake.

`os.path.expanduser` does not raise: where it cannot expand, it hands the `~`
straight back. That is not a usable path either, and the difference matters by
call site. Somewhere to read from can be left as it is, because everything that
does that immediately asks `.exists()` and gets the right answer. Somewhere to
*write* cannot: `~/.config/thebleep` would be created as a directory actually
named `~` in whatever the working directory happened to be.

"""

import os
from pathlib import Path


def expanduser(path):
    """`path` as a `Path`, with a leading `~` expanded where that is possible."""
    return Path(os.path.expanduser(str(path)))


def _is_expanded(path):
    """Whether `expanduser` found a home directory to expand to."""
    return not str(path).startswith('~')


def writable(path, purpose):
    """`path`, or somewhere in the temporary directory if it is not usable.

    Somewhere to keep settings and caches is not optional, so with no home
    directory to put them in this falls back rather than failing. Nothing
    survives a reboot there, which is the honest outcome of having nowhere of
    one's own to write to, and it beats creating a directory named `~` wherever
    the user happened to be standing.

    """
    if _is_expanded(path):
        return path

    # Lazily, and defensively: this is the path nobody takes, and `getuser`
    # consults the very environment that is missing.
    try:
        import getpass
        import tempfile

        who = getpass.getuser()
    except Exception:                                        # noqa: BLE001
        who = 'user'

    return Path(tempfile.gettempdir()).joinpath(
        'thebleep-{}-{}'.format(purpose, who))
