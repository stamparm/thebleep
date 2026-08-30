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
MAX_CARGO_TOML_BYTES = 1024 * 1024
MAX_PYPROJECT_BYTES = 1024 * 1024
MAX_TASKFILE_BYTES = 1024 * 1024
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


def _read_cargo_toml(path):
    try:
        if os.path.getsize(path) > MAX_CARGO_TOML_BYTES:
            return None
        with open(path, encoding='utf-8') as handle:
            value = handle.read(MAX_CARGO_TOML_BYTES + 1)
    except (EnvironmentError, UnicodeError):
        return None

    return value if len(value.encode('utf-8')) <= MAX_CARGO_TOML_BYTES else None


def cargo_bins(start=None):
    """Return explicitly named binaries from the nearest Cargo.toml.

    Cargo manifests are TOML, but importing a parser just for this optional
    hint would add a runtime dependency.  This reads only simple ``[[bin]]``
    blocks and quoted ``name`` assignments; workspace inheritance, generated
    names and other TOML features are intentionally left to Cargo itself.
    """
    path = find_up('Cargo.toml', start)
    if path is None:
        return None

    source = _read_cargo_toml(path)
    if source is None:
        return None

    found = []
    in_bin = False
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('[['):
            in_bin = stripped.split(']]', 1)[0] == '[[bin'
            continue
        if stripped.startswith('['):
            in_bin = False
            continue
        if not in_bin:
            continue

        match = re.match(r'name\s*=\s*([\"\'])([^\"\'\r\n]+)\1',
                         stripped)
        if match and _just_name(match.group(2)) and match.group(2) not in found:
            found.append(match.group(2))

    return found


def _read_pyproject(path):
    try:
        if os.path.getsize(path) > MAX_PYPROJECT_BYTES:
            return None
        with open(path, encoding='utf-8') as handle:
            value = handle.read(MAX_PYPROJECT_BYTES + 1)
    except (EnvironmentError, UnicodeError):
        return None

    return value if len(value.encode('utf-8')) <= MAX_PYPROJECT_BYTES else None


def poetry_scripts(start=None):
    """Return static script names from the nearest Poetry-style pyproject."""
    path = find_up('pyproject.toml', start)
    if path is None:
        return None

    source = _read_pyproject(path)
    if source is None:
        return None

    found = []
    section = None
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped.strip('[]')
            continue
        if section not in ('project.scripts', 'tool.poetry.scripts'):
            continue

        match = re.match(
            r'(?:"([^"\r\n]+)"|([A-Za-z0-9_.-]+))\s*=', stripped)
        name = (match.group(1) or match.group(2)) if match else None
        if name and _usable_name(name) and name not in found:
            found.append(name)

    return found


def _taskfile(start=None):
    """Return the nearest Taskfile using Task's conventional names."""
    directory = os.path.abspath(start or os.getcwd())
    while True:
        for filename in ('Taskfile.yml', 'Taskfile.yaml'):
            candidate = os.path.join(directory, filename)
            if os.path.isfile(candidate):
                return candidate

        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def _read_taskfile(path):
    try:
        if os.path.getsize(path) > MAX_TASKFILE_BYTES:
            return None
        with open(path, encoding='utf-8') as handle:
            value = handle.read(MAX_TASKFILE_BYTES + 1)
    except (EnvironmentError, UnicodeError):
        return None

    return value if len(value.encode('utf-8')) <= MAX_TASKFILE_BYTES else None


_TASK_NAME = re.compile(
    r'^(?:"([^"\r\n]+)"|\'([^\'\r\n]+)\'|'
    r'([A-Za-z0-9_.:/+!?-]+))\s*:')


def _task_name(name):
    """Whether a Taskfile key is static and safe to rank."""
    return (_just_name(name) and '{{' not in name and '}}' not in name)


def task_names(start=None):
    """Return static task names from the nearest Taskfile.

    This is intentionally a small YAML reader. Taskfiles can include other
    files and calculate task names, but the top-level ``tasks`` mapping is
    plain enough to read without adding a YAML dependency or executing any
    project code. Only keys at the mapping's own indentation are candidates;
    nested ``cmds``, ``vars`` and dependency data cannot become task names.
    """
    path = _taskfile(start)
    if path is None:
        return None

    source = _read_taskfile(path)
    if source is None:
        return None

    found = []
    in_tasks = False
    task_indent = None
    for line in source.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue

        indent = len(line) - len(line.lstrip(' '))
        stripped = line.strip()
        if indent == 0:
            in_tasks = bool(re.match(r'^tasks\s*:\s*(?:#.*)?$', stripped))
            task_indent = None
            continue
        if not in_tasks:
            continue
        if task_indent is None:
            task_indent = indent
        if indent != task_indent:
            continue

        match = _TASK_NAME.match(stripped)
        if not match:
            continue
        name = next(value for value in match.groups() if value is not None)
        if _task_name(name) and name not in found:
            found.append(name)

    return found
