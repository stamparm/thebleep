# -*- encoding: utf-8 -*-

"""Small, read-only sources of vocabulary from the current project.

Project files are better completion knowledge than a guess from ``PATH`` or a
second invocation of the package manager.  This module only reads bounded,
declared metadata: it never imports a project or runs a script.
"""

import json
import os
import re


MAX_JSON_BYTES = 1024 * 1024
MAX_MAKEFILE_BYTES = 1024 * 1024
MAX_JUSTFILE_BYTES = 1024 * 1024
_MAKE_TARGET = re.compile(r'^(?![ \t])([^:#=\s][^:#]*?)\s*:(?!=)')
_JUST_RECIPE = re.compile(
    r'^(?:\[[^\]\r\n]+\]\s*)?'
    r'([A-Za-z0-9_+!?-]+)(?:\s+[^:\r\n]*)?:(?!=)')
_JUST_ALIAS = re.compile(
    r'^alias\s+([A-Za-z0-9_./+!?-]+)\s*:?=')


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


def _makefile(start=None):
    """Return the nearest Makefile using make's standard name order."""
    directory = os.path.abspath(start or os.getcwd())
    while True:
        for filename in ('GNUmakefile', 'makefile', 'Makefile'):
            candidate = os.path.join(directory, filename)
            if os.path.isfile(candidate):
                return candidate

        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def _read_makefile(path):
    try:
        if os.path.getsize(path) > MAX_MAKEFILE_BYTES:
            return None
        with open(path, encoding='utf-8') as handle:
            value = handle.read(MAX_MAKEFILE_BYTES + 1)
    except (EnvironmentError, UnicodeError):
        return None

    return value if len(value.encode('utf-8')) <= MAX_MAKEFILE_BYTES else None


def _make_target_name(name):
    """Whether a static target is safe and useful as a typo candidate."""
    return (bool(name) and not name.startswith('.') and '%' not in name
            and '$' not in name and '\\' not in name
            and '\x00' not in name and '\r' not in name
            and '\n' not in name)


def make_targets(start=None):
    """Return explicit target names from the nearest readable Makefile.

    This intentionally understands only ordinary, static target declarations.
    Dynamic ``eval``/pattern/variable targets are not guessed; an empty or
    ambiguous source is safer than offering a recipe the file did not clearly
    name.
    """
    path = _makefile(start)
    if path is None:
        return None

    source = _read_makefile(path)
    if source is None:
        return None

    found = []
    for line in source.splitlines():
        match = _MAKE_TARGET.match(line)
        if not match:
            continue

        names = match.group(1).split()
        if names == ['.PHONY']:
            names = line[match.end():].split()
        for name in names:
            if _make_target_name(name) and name not in found:
                found.append(name)

    return found


def _read_justfile(path):
    try:
        if os.path.getsize(path) > MAX_JUSTFILE_BYTES:
            return None
        with open(path, encoding='utf-8') as handle:
            value = handle.read(MAX_JUSTFILE_BYTES + 1)
    except (EnvironmentError, UnicodeError):
        return None

    return value if len(value.encode('utf-8')) <= MAX_JUSTFILE_BYTES else None


def _justfile(start=None):
    """Return the nearest Justfile using just's conventional names."""
    directory = os.path.abspath(start or os.getcwd())
    while True:
        for filename in ('Justfile', 'justfile'):
            candidate = os.path.join(directory, filename)
            if os.path.isfile(candidate):
                return candidate

        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def _just_name(name):
    """Whether a static recipe or alias is safe and useful as a candidate."""
    return (bool(name) and '%' not in name and '$' not in name
            and '\\' not in name and '\x00' not in name
            and '\r' not in name and '\n' not in name)


def just_recipes(start=None):
    """Return static recipe and alias names from the nearest Justfile.

    Justfiles can compute names through interpolation and imports can bring in
    other files.  Those are deliberately outside this small parser: offering
    only names visibly declared in one bounded file keeps correction local and
    avoids executing or interpreting project code.
    """
    path = _justfile(start)
    if path is None:
        return None

    source = _read_justfile(path)
    if source is None:
        return None

    found = []
    for line in source.splitlines():
        match = _JUST_RECIPE.match(line)
        name = match.group(1) if match else None
        if name is None:
            alias = _JUST_ALIAS.match(line)
            name = alias.group(1) if alias else None
        if name and _just_name(name) and name not in found:
            found.append(name)

    return found
