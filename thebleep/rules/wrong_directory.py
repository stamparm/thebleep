# -*- encoding: utf-8 -*-

"""`npm run build` in the wrong directory -> `cd app && npm run build`.

The command was right; the directory was not. Every project tool has a way of
saying so, and none of them says where the project is:

    $ git status
    fatal: not a git repository (or any of the parent directories): .git
    $ npm run build
    npm error enoent Could not read package.json: Error: ENOENT: ...
    $ make build
    make: *** No rule to make target 'build'.  Stop.
    $ cargo build
    error: could not find `Cargo.toml` in `/home/u/src` or any parent directory

The answer is usually one directory away, and this rule goes and looks:
children two levels down, and for the tools that do not search upwards
themselves (make, mvn, docker compose, terraform) the parent as well. A
directory qualifies when it holds the tool's own file -- `.git`,
`package.json`, a `Makefile`, `Cargo.toml` -- and, where the failure named a
script, target or recipe, when that file *declares* it. `make build` is not
answered with a directory whose Makefile has no `build`.

Everything read is the same bounded, declared metadata `project_context`
already reads for the typo rules; nothing is run. When the failure named
nothing to check against, only an *unambiguous* answer is given: a directory of
twenty git checkouts is not a suggestion, it is a guess, and a wrong `cd` one
keystroke from running is worse than silence.

Fixtures: git 2.43.0, GNU Make 4.3, npm 11.19.0, pnpm 11.25.0, yarn 1.22.17,
cargo 1.98.0, Maven 3.x, Docker Compose v2.27.0, just 1.26.0, go-task,
uv 0.9.30, Poetry 2.4.2 and Terraform 1.9, each run in an empty directory.

"""

import os
import re

from thebleep import project_context
from thebleep.shells import shell
from thebleep.types import Suggestion
from thebleep.utils import for_app

priority = 900

# How deep below the working directory to look, how many directories to look
# at in total before giving up, and the directories never worth entering.
DEPTH = 2
VISIT_LIMIT = 400
SKIPPED = frozenset(('node_modules', 'vendor', 'target', '__pycache__',
                     'venv', 'site-packages'))

# What the failure named, when it named anything.
MISSING_SCRIPT = re.compile(r'Missing script:\s*"?([^"\r\n]+?)"?\s*$', re.M)
MISSING_TARGET = re.compile(r"No rule to make target ['\"]([^'\"]+)['\"]")
MISSING_RECIPE = re.compile(r'does not contain recipe [`\']([^`\'\r\n]+)')


def _first_argument(command, after=()):
    """The first word after the program (and `after`) that is not an option."""
    parts = command.script_parts[1:]
    for word in after:
        if word in parts:
            parts = parts[parts.index(word) + 1:]
            break
    for part in parts:
        if not part.startswith('-'):
            return part
    return None


def _script_name(command):
    found = MISSING_SCRIPT.search(command.output)
    if found:
        return found.group(1).strip()
    parts = command.script_parts
    if len(parts) > 1 and parts[1] in ('run', 'run-script'):
        return _first_argument(command, after=('run', 'run-script'))
    if len(parts) > 1 and parts[1] in ('test', 'start', 'stop', 'restart'):
        return parts[1]
    return None


def _make_target(command):
    found = MISSING_TARGET.search(command.output)
    return found.group(1) if found else _first_argument(command)


def _just_recipe(command):
    found = MISSING_RECIPE.search(command.output)
    return found.group(1) if found else _first_argument(command)


def _has_any(directory, names):
    return any(os.path.isfile(os.path.join(directory, name)) for name in names)


def _is_git_checkout(directory):
    # A worktree's `.git` is a file; a checkout's is a directory.
    return os.path.exists(os.path.join(directory, '.git'))


def _has_terraform_files(directory):
    try:
        return any(name.endswith('.tf') for name in os.listdir(directory))
    except OSError:
        return False


def _declares(reader, directory, name):
    """Whether the project file in `directory` declares `name`, read by
    `reader`. None from the reader means nothing readable was there."""
    declared = reader(directory)
    return declared is not None and name in declared


# app -> (needles any of which is the failure, is this directory the project,
#         what was named or None, does the directory declare it)
def _cases():
    return {
        'git': (
            ('not a git repository',),
            _is_git_checkout, None, None, False),
        'make': (
            ('no makefile found', 'No rule to make target'),
            lambda d: _has_any(d, ('GNUmakefile', 'makefile', 'Makefile')),
            _make_target, project_context.make_targets, True),
        'npm': (
            ('Could not read package.json', 'Missing script:'),
            lambda d: _has_any(d, ('package.json',)),
            _script_name, project_context.package_scripts, False),
        'pnpm': (
            ('No package.json', 'Missing script:'),
            lambda d: _has_any(d, ('package.json',)),
            _script_name, project_context.package_scripts, False),
        'yarn': (
            ("Couldn't find a package.json file",),
            lambda d: _has_any(d, ('package.json',)),
            _script_name, project_context.package_scripts, False),
        'cargo': (
            ('could not find `Cargo.toml`',),
            lambda d: _has_any(d, ('Cargo.toml',)), None, None, False),
        'mvn': (
            ('there is no POM in this directory',),
            lambda d: _has_any(d, ('pom.xml',)), None, None, True),
        'docker': (
            ('no configuration file provided',),
            lambda d: _has_any(d, ('compose.yaml', 'compose.yml',
                                   'docker-compose.yaml',
                                   'docker-compose.yml')),
            None, None, True),
        'just': (
            ('No justfile found', 'does not contain recipe'),
            lambda d: _has_any(d, ('justfile', 'Justfile', '.justfile')),
            _just_recipe, project_context.just_recipes, False),
        'task': (
            ('No Taskfile found',),
            lambda d: _has_any(d, ('Taskfile.yml', 'Taskfile.yaml',
                                   'taskfile.yml', 'taskfile.yaml',
                                   'Taskfile.dist.yml', 'Taskfile.dist.yaml')),
            lambda c: _first_argument(c), project_context.task_names, False),
        'uv': (
            ('No `pyproject.toml` found',),
            lambda d: _has_any(d, ('pyproject.toml',)), None, None, False),
        'poetry': (
            ('could not find a pyproject.toml file',),
            lambda d: _has_any(d, ('pyproject.toml',)), None, None, False),
        'terraform': (
            ('No configuration files',),
            _has_terraform_files, None, None, True),
    }


@for_app('git', 'make', 'npm', 'pnpm', 'yarn', 'cargo', 'mvn', 'docker',
         'just', 'task', 'uv', 'poetry', 'terraform')
def match(command):
    return ('not a git repository' in command.output
            or 'no makefile found' in command.output
            or 'No rule to make target' in command.output
            or 'Could not read package.json' in command.output
            or 'Missing script:' in command.output
            or 'No package.json' in command.output
            or "Couldn't find a package.json file" in command.output
            or 'could not find `Cargo.toml`' in command.output
            or 'there is no POM in this directory' in command.output
            or 'no configuration file provided' in command.output
            or 'No justfile found' in command.output
            or 'does not contain recipe' in command.output
            or 'No Taskfile found' in command.output
            or 'No `pyproject.toml` found' in command.output
            or 'could not find a pyproject.toml file' in command.output
            or 'No configuration files' in command.output)


def _app(command):
    parts = command.script_parts
    return os.path.basename(parts[0]) if parts else None


def _nearby(cwd, include_parent):
    """Directories worth looking in, nearest first, bounded and in name order."""
    seen = 0
    if include_parent:
        parent = os.path.dirname(cwd)
        if parent and parent != cwd:
            yield parent, os.pardir
    frontier = [(cwd, '', 0)]
    while frontier:
        directory, relative, depth = frontier.pop(0)
        if depth >= DEPTH:
            continue
        try:
            with os.scandir(directory) as entries:
                children = sorted(
                    (entry.name for entry in entries
                     if _enterable(entry)), key=str)
        except OSError:
            continue
        for name in children:
            seen += 1
            if seen > VISIT_LIMIT:
                return
            path = os.path.join(directory, name)
            here = os.path.join(relative, name) if relative else name
            yield path, here
            frontier.append((path, here, depth + 1))


def _enterable(entry):
    try:
        return (entry.is_dir(follow_symlinks=False)
                and not entry.name.startswith('.')
                and entry.name not in SKIPPED)
    except OSError:
        return False


def get_new_command(command):
    app = _app(command)
    case = _cases().get(app)
    if case is None or not command.output:
        return []
    needles, is_project, named, declared_by, include_parent = case
    if not any(needle in command.output for needle in needles):
        return []
    if app == 'docker' and 'compose' not in command.script_parts:
        return []

    name = named(command) if named else None
    if named and not name:
        # The failure named nothing and the command named nothing: with no
        # declared item to check, only an unambiguous directory will do.
        declared_by = None

    try:
        cwd = os.getcwd()
    except OSError:
        return []

    found = []
    for path, relative in _nearby(cwd, include_parent):
        if not is_project(path):
            continue
        if declared_by is not None:
            if not _declares(declared_by, path, name):
                continue
            found.append((relative, u'{} declares {}'.format(
                _shown(relative, is_project, path), name)))
        else:
            found.append((relative, u'{} is where the {} project is'.format(
                relative, app)))

    if not found:
        return []
    if declared_by is None and len(found) != 1:
        return []

    confidence = 0.9 if declared_by is not None else 0.8
    if len(found) > 1:
        confidence = 0.7
    return [Suggestion(shell.and_(u'cd {}'.format(shell.quote(relative)),
                                  command.script),
                       confidence=confidence, evidence=(evidence,))
            for relative, evidence in found[:3]]


def _shown(relative, is_project, path):
    """`app/package.json`, or just the directory when the file has no one
    canonical name."""
    for name in ('package.json', 'Makefile', 'makefile', 'GNUmakefile',
                 'justfile', 'Justfile', 'Taskfile.yml', 'Taskfile.yaml'):
        if os.path.isfile(os.path.join(path, name)):
            return os.path.join(relative, name)
    return relative
