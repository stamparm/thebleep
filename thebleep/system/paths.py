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


# Where the fallback went when the predictable name was somebody else's, by
# purpose. Once per process: the rule pack lives under the cache directory and
# has to be found again.
_UNPREDICTABLE = {}


def _is_ours(path):
    """Whether `path` is a directory this user owns, tightening it if it is.

    `None` if it is not there at all, so the caller can tell "make it" from
    "somebody else got here first".

    Ownership is the question that matters and the one that cannot be repaired.
    A directory this user owns but that the group can write to is one an earlier
    release created under the default umask, and the answer to that is a
    `chmod`, not a refusal -- refusing it would mean a fresh directory and a
    rebuilt rule pack on every single correction, forever.

    """
    import stat

    try:
        info = os.stat(str(path))
    except FileNotFoundError:
        return None
    except OSError:
        return False

    if not stat.S_ISDIR(info.st_mode):
        return False

    if not hasattr(os, 'geteuid'):
        # Windows, where the mode bits mean nothing and the ACL a directory
        # inherits under the per-user temporary directory is the answer.
        return True

    if info.st_uid != os.geteuid():
        return False

    if info.st_mode & 0o022:
        try:
            os.chmod(str(path), 0o700)
        except OSError:
            return False

    return True


def writable(path, purpose):
    """`path`, or somewhere in the temporary directory if it is not usable.

    Somewhere to keep settings and caches is not optional, so with no home
    directory to put them in this falls back rather than failing. Nothing
    survives a reboot there, which is the honest outcome of having nowhere of
    one's own to write to, and it beats creating a directory named `~` wherever
    the user happened to be standing.

    The fallback is `0700` and checked, which it was not. `/tmp` is shared and
    `thebleep-cache-<user>` is a name anybody can work out -- and what goes in
    the cache directory is `rulepack`'s pack file, which is `marshal.loads`ed
    and `exec`ed on the next correction. So a local attacker who created that
    directory first, with a pack of their own in it, ran their code as this user.
    A directory that is there and is somebody else's is refused rather than
    used: an unpredictable name instead, which costs a rebuilt pack per run and
    is the right price.

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

    candidate = Path(tempfile.gettempdir()).joinpath(
        'thebleep-{}-{}'.format(purpose, who))

    ours = _is_ours(candidate)
    if ours is None:
        try:
            os.makedirs(str(candidate), mode=0o700)
            return candidate
        except OSError:
            # Lost a race with something. Ask again rather than assume.
            ours = _is_ours(candidate)

    if ours:
        return candidate

    # Somebody else's. An unpredictable name instead, made once per process so
    # that everything asking where to write agrees on the answer -- the rule
    # pack lives under the cache directory and has to be found again.
    if purpose not in _UNPREDICTABLE:
        try:
            _UNPREDICTABLE[purpose] = Path(
                tempfile.mkdtemp(prefix='thebleep-{}-'.format(purpose)))
        except Exception:                                    # noqa: BLE001
            # Nowhere at all. The caller's own error handling takes it from
            # here -- every writer of these paths treats a failure as "no
            # cache".
            return candidate

    return _UNPREDICTABLE[purpose]
