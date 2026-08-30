# -*- encoding: utf-8 -*-

"""Small, read-only sources of vocabulary from the current project.

Project files are better completion knowledge than a guess from ``PATH`` or a
second invocation of the package manager.  This module only reads bounded,
declared metadata: it never imports a project or runs a script.
"""

import json
import os


MAX_JSON_BYTES = 1024 * 1024


def find_up(filename, start=None):
    """Return the nearest ``filename`` at or above ``start``, if any."""
    directory = os.path.abspath(start or os.getcwd())
    while True:
        candidate = os.path.join(directory, filename)
        if os.path.isfile(candidate):
            return candidate

        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def _read_json(path):
    """Return a JSON object from ``path`` or ``None`` when it is unusable."""
    try:
        if os.path.getsize(path) > MAX_JSON_BYTES:
            return None
        with open(path, encoding='utf-8') as handle:
            value = handle.read(MAX_JSON_BYTES + 1)
    except (EnvironmentError, UnicodeError):
        return None

    if len(value.encode('utf-8')) > MAX_JSON_BYTES:
        return None

    try:
        parsed = json.loads(value)
    except (ValueError, MemoryError, RecursionError):
        return None

    return parsed if isinstance(parsed, dict) else None


def _usable_name(name):
    """Whether a manifest key can be safely used as one command argument."""
    return isinstance(name, str) and bool(name) \
        and '\x00' not in name and '\r' not in name and '\n' not in name


def package_scripts(start=None):
    """Return script names from the nearest ``package.json``.

    ``None`` means no readable manifest was found; an empty list means the
    manifest was valid but declared no usable scripts.  Keeping that distinction
    lets callers fall back to a tool's own output only when there is no source
    of project metadata to read.
    """
    path = find_up('package.json', start)
    if path is None:
        return None

    package = _read_json(path)
    if package is None:
        return None

    scripts = package.get('scripts')
    if not isinstance(scripts, dict):
        return []

    return [name for name in scripts if _usable_name(name)]
