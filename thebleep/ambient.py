# -*- encoding: utf-8 -*-

"""`git satus` -> `git status` before anything runs.

The `--ambient` bindings corrected one thing: a first word the shell had never
heard of. `git satus` ran and failed as it always had, because `git` exists
and the shell cannot know what git will think of `satus`. The shell cannot,
but the machine can: git documents its commands one manual page each, and a
page named `git-satus` is not among them. `thebleep.vocabulary` already reads
that list, and the fish completions, for the rules that run after a failure;
this reads the same list before the line runs.

The question the shell asks here is different from the one it asks about an
unknown program, and so is the standard. A line the shell knows how to run is
about to be rewritten without the program having said a word, so nothing is
offered unless it is certain the line would fail:

- the program documents its subcommands at all, and the word right after it
  is not one of them;
- it is not one the manual could not know about either: `git-lg` on `PATH`
  (git, cargo and kubectl all find subcommands that way), a git alias in any
  of git's configuration files, a docker CLI plugin;
- it is not an abbreviation of one -- `npm i`, `npm inst` -- for the tools
  that accept those (`ABBREVIATING`), nor shorter than three letters for
  any tool. Everywhere else `git dif` and `git statu` are a dropped key, and
  fail as surely as `git satus` does;
- and one documented subcommand is within the edit distance `matching` holds
  everything else to.

Only the word right after the program, on a line that is one simple command
with no option in front of it: `git -C .. status` is left alone, and so is
`sudo git satus`. Nothing here runs a program: the manual, the completions,
the configuration files and `PATH` are files on this machine.

"""

import os
import re

from . import matching, vocabulary
from .utils import which

# Where docker looks for `docker-<name>` plugins; `docker compose` and
# `docker buildx` have no manual page of their own.
DOCKER_PLUGIN_DIRECTORIES = ('~/.docker/cli-plugins',
                             '/usr/local/lib/docker/cli-plugins',
                             '/usr/local/libexec/docker/cli-plugins',
                             '/usr/lib/docker/cli-plugins',
                             '/usr/libexec/docker/cli-plugins')

MAX_CONFIG = 256 * 1024
MAX_CONFIG_FILES = 8

_SECTION = re.compile(r'^\s*\[\s*([^\]\s]+)(?:\s+"[^"]*")?\s*\]')
_KEY = re.compile(r'^\s*([^\s=#;]+)\s*=\s*(.*?)\s*$')
_WORD = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]*$')
# Tools that take a shortened subcommand, some of them resolving an ambiguous
# one by their own order (`ip a` is `ip address`), so a prefix of a real
# subcommand may be exactly what was meant. Listing one that does not costs a
# correction; leaving out one that does rewrites a line that worked.
ABBREVIATING = frozenset(('npm', 'pnpm', 'yarn', 'hg', 'ip', 'nmcli',
                          'bridge', 'tc', 'gem', 'svn', 'bluetoothctl'))
MIN_PREFIX = 3

_WRAPPERS = frozenset(('sudo', 'doas', 'env', 'command', 'exec', 'nohup',
                       'time', 'nice', 'xargs', 'watch'))


def _git_config_files(cwd):
    """git's configuration files, outermost first, where they exist."""
    home = os.path.expanduser('~')
    files = [os.environ.get('GIT_CONFIG_SYSTEM') or '/etc/gitconfig',
             os.environ.get('GIT_CONFIG_GLOBAL') or '',
             os.path.join(os.environ.get('XDG_CONFIG_HOME')
                          or os.path.join(home, '.config'), 'git', 'config'),
             os.path.join(home, '.gitconfig')]
    directory = os.path.abspath(cwd or os.getcwd())
    while True:
        marker = os.path.join(directory, '.git')
        if os.path.isdir(marker):
            files.append(os.path.join(marker, 'config'))
            break
        if os.path.isfile(marker):
            # A worktree or a submodule: `gitdir: <path>` points at the
            # repository's own directory.
            try:
                with open(marker, encoding='utf-8', errors='replace') as f:
                    line = f.readline(4096).strip()
            except OSError:
                line = ''
            if line.startswith('gitdir:'):
                target = line[len('gitdir:'):].strip()
                files.append(os.path.join(
                    os.path.normpath(os.path.join(directory, target)),
                    'config'))
            break
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return [path for path in files if path and os.path.isfile(path)]


def git_aliases(cwd=None):
    """The names git would accept as aliases here, or None if a configuration
    file could not be read -- in which case nothing is certain."""
    names = set()
    queue = _git_config_files(cwd)
    seen = set()
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        if len(seen) > MAX_CONFIG_FILES:
            return None
        try:
            if os.path.getsize(path) > MAX_CONFIG:
                return None
            with open(path, encoding='utf-8', errors='replace') as handle:
                lines = handle.read(MAX_CONFIG + 1).splitlines()
        except OSError:
            return None
        section = None
        for line in lines:
            found = _SECTION.match(line)
            if found:
                section = found.group(1).lower()
                continue
            found = _KEY.match(line)
            if not found:
                continue
            key, value = found.groups()
            if section == 'alias':
                names.add(key)
            elif section in ('include', 'includeif') and key == 'path':
                value = os.path.expanduser(value)
                if not os.path.isabs(value):
                    value = os.path.join(os.path.dirname(path), value)
                if os.path.isfile(value):
                    queue.append(os.path.normpath(value))
    return names


def _known_elsewhere(program, word, cwd):
    """Whether `program word` could work although the manual has no page for
    it. None when that could not be determined."""
    if which(u'{}-{}'.format(program, word)):
        return True
    if program == 'git':
        aliases = git_aliases(cwd)
        if aliases is None or word in aliases:
            return True
    if program == 'docker':
        for directory in DOCKER_PLUGIN_DIRECTORIES:
            if os.path.exists(os.path.join(os.path.expanduser(directory),
                                           'docker-' + word)):
                return True
    return False


def known_program_correction(script, cwd=None):
    """The line with its subcommand put right, or None.

    `script` is a line whose first word the shell knows how to run; the
    answer is what the ambient check puts in its place, and nothing is the
    usual answer.

    """
    from .shells import shell
    from .types import Command
    from .utils import command_word_index, replace_argument

    command = Command(script, None)
    model = command.command_model
    if not model.complete or len(model.segments) != 1:
        return None
    parts = command.script_parts
    start = command_word_index(parts)
    if start != 0 or len(parts) < 2:
        return None
    program, word = parts[0], parts[1]
    if program in _WRAPPERS or '/' in program or not _WORD.match(word):
        return None
    candidates = vocabulary.subcommands(program)
    if not candidates or word in candidates:
        return None
    # Caps lock, or Shift held a key too long: `git STATUS`.
    if word != word.lower() and word.lower() in candidates:
        return replace_argument(script, word, word.lower())
    if any(candidate.startswith(word) for candidate in candidates) and (
            program in ABBREVIATING or len(word) < MIN_PREFIX):
        return None
    scored = matching.rank_with_distance(word, candidates)
    if not scored:
        return None
    # One slip of a finger before an equally distant edit nobody makes:
    # `npm teat` is `test` (`a` beside `s`), not `team`.
    best = (matching.plausible_slips(word, scored) or [scored[0][0]])[0]
    if _known_elsewhere(program, word, cwd):
        return None
    fixed = replace_argument(script, word, shell.quote(best))
    return fixed if fixed != script else None
