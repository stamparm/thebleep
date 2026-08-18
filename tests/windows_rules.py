# -*- coding: utf-8 -*-

"""Putting a POSIX machine in Windows' position, for the parts that can be.

Four rounds of Windows-only CI failures were all the same kind of thing: code
that asks a question POSIX answers generously and Windows does not, or a test
whose expectation was written down as the POSIX answer. None of them needed
Windows to find. They needed the three differences below to be present.

Enabled with `pytest --windows-rules`, and deliberately not by default: it makes
a POSIX machine lie, and the suite has to pass honestly as well.

What this is not: a Windows emulator. It says nothing about `subprocess`, path
separators, case-insensitivity or the console, and nothing at all about speed --
a number measured on ext4 is not a Windows number, and `bench/scan_cost.py` is
where that question goes. Passing here does not mean Windows passes. Failing here
means Windows fails.

"""

import os
import os.path
import tempfile

# Whether the code under test is answering Windows' questions. Read this rather
# than `os.name` wherever a test's *expectation* differs by platform, so the
# expectation moves with the fake.
_applied = False


def applied():
    return os.name == 'nt' or _applied


def _expanduser(path):
    """`os.path.expanduser` with Windows' rules: only the environment answers.

    POSIX falls back to the password database, so `~` expands with `HOME` unset
    and the no-home-directory path cannot be reached. `ntpath` has no such
    fallback: nothing in the environment means the `~` comes straight back, and
    then anything that treats the result as a real path is creating a directory
    called `~`.

    """
    text = str(path)
    if text != '~' and not text.startswith(('~/', '~\\')):
        return path
    home = os.environ.get('USERPROFILE') or os.environ.get('HOME')
    if not home:
        return path
    return home + text[1:]


def _access(real):
    """`os.access` with Windows' answer to "could I run this".

    There is no executable bit, so `X_OK` is only asking whether the file is
    there. Anything that decides what is a command by asking this keeps the
    README next to the program.

    """
    def access(path, mode, **kwargs):
        if mode & os.X_OK:
            mode = (mode & ~os.X_OK) | os.F_OK
        return real(path, mode, **kwargs)

    return access


def _short_name_temporary_directory():
    """A temporary directory whose name holds a tilde, as Windows' does.

    The runner's is `C:\\Users\\RUNNER~1\\AppData\\Local\\Temp`, an 8.3 short
    name, which is enough to fail any test that looks for an unexpanded `~` by
    searching the whole string for one.

    """
    directory = os.path.join(tempfile.gettempdir(), 'RUNNER~1')
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        return None
    return directory


def install():
    """Applies all three, for the rest of the session."""
    global _applied

    os.path.expanduser = _expanduser
    os.access = _access(os.access)
    short = _short_name_temporary_directory()
    if short:
        tempfile.tempdir = short
    _applied = True
    return {'expanduser': 'environment only',
            'X_OK': 'existence only',
            'tempdir': short}
