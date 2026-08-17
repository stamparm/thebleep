"""A small on-disk cache for answers that are expensive to work out again.

`shelve` was doing this job, and it costs `dbm` and `pickle` at import time
before it has stored anything. What the app actually caches is plain data —
lists of names, a few booleans — so this stores it with `marshal` in one file
per subject and skips both.

Like the rule pack, this is only ever an optimisation: an unreadable or stale
cache costs time, never correctness.
"""

import marshal
import os
import time
from .system import Path

FORMAT = 1


def _directory():
    cache_home = os.environ.get('XDG_CACHE_HOME') or '~/.cache'
    return Path(cache_home).expanduser().joinpath('thebleep')


def path_for(name):
    return _directory().joinpath('{}.cache'.format(name))


def load(name, fingerprint, max_age=None):
    """The cached value stored under `name`, if it was stored for this input.

    The fingerprint is whatever makes the answer valid — a set of paths and
    their modification times, a version, a setting. A different one is a miss.

    `max_age`, in seconds, bounds how wrong a fingerprint is allowed to be.
    Directory timestamps come from a coarse clock, so a change made in the same
    clock tick as the last read would otherwise go unnoticed indefinitely.

    """
    try:
        with path_for(name).open('rb') as handle:
            cached = marshal.load(handle)
    except Exception:
        return None
    if not isinstance(cached, dict) or cached.get('format') != FORMAT:
        return None
    if cached.get('fingerprint') != fingerprint:
        return None
    if max_age is not None:
        saved_at = cached.get('saved_at')
        if not saved_at or time.time() - saved_at > max_age:
            return None
    return cached.get('value')


def save(name, fingerprint, value):
    """Stores a value, or quietly gives up when the cache isn't writable."""
    path = path_for(name)
    temp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.parent.joinpath('{}.{}.tmp'.format(path.name, os.getpid()))
        with temp.open('wb') as handle:
            marshal.dump({'format': FORMAT, 'fingerprint': fingerprint,
                          'saved_at': time.time(), 'value': value}, handle)
        os.replace(str(temp), str(path))
    except Exception:
        if temp is not None:
            try:
                os.unlink(str(temp))
            except OSError:
                pass
    return value


def clear():
    """Removes every cache file. Returns how many were removed."""
    removed = 0
    try:
        for entry in _directory().glob('*.cache'):
            try:
                os.unlink(str(entry))
                removed += 1
            except OSError:
                pass
    except Exception:
        pass
    return removed
