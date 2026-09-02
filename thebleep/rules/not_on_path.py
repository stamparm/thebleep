# -*- encoding: utf-8 -*-

"""`cargo build` -> `/home/u/.cargo/bin/cargo build`: installed, but not on PATH.

The commonest `command not found` on a developer's machine is not a typo. The
program is there. It was put somewhere the installer told you about once, in
a line you did not add to your shell's startup file, or it belongs to the
project you are standing in and was never meant to be on `PATH` at all:

    $ cargo build
    bash: cargo: command not found       ~/.cargo/bin/cargo, from rustup
    $ prettier --check .
    zsh: command not found: prettier     ./node_modules/.bin/prettier
    $ pytest -q
    fish: Unknown command: pytest        .venv/bin/pytest

Until now the answer to all three was a guess at a *different* program one
edit away -- `cargo` has none, so nothing; `pytest` might get `pytest`'s
system copy if there was one. This rule looks where installers put things and
where projects keep them, and when the program is there under exactly the
name typed, it says so and offers two things: the command with the path
written out, which runs now, and the same command with the directory put on
`PATH` first, which fixes the rest of the session.

Project directories come first (a `.venv/bin/pytest` is the one you meant,
not `~/.local/bin/pytest`), the nearest one first, and never past the
repository root. Nothing is written anywhere: the `export` is part of the
suggested command, in your shell's own syntax, and lasts as long as the
shell does. Putting it in a startup file is your call, and the line to put
there is the one on the screen.

The name has to match exactly. This rule is not about typos -- `no_command`
is -- and it runs *before* it, because a program that exists under the name
you typed beats a program one edit away that does not need a path.

"""

import os

from thebleep.shells import shell
from thebleep.types import Suggestion
from thebleep.utils import command_word_index, which

priority = 2000
requires_output = False

# Where installers put programs and forget to tell the shell. `*` is a glob,
# for the version managers that keep one directory per version.
HOMES = (
    '~/.cargo/bin', '~/go/bin', '~/.local/bin', '~/bin', '~/.npm-global/bin',
    '~/.npm/bin', '~/.yarn/bin', '~/.bun/bin', '~/.deno/bin', '~/.volta/bin',
    '~/.pyenv/shims', '~/.rbenv/shims', '~/.nodenv/shims', '~/.asdf/shims',
    '~/.local/share/mise/shims', '~/.rye/shims', '~/.pixi/bin',
    '~/.nvm/versions/node/*/bin', '~/.gem/ruby/*/bin', '~/.local/share/gem/ruby/*/bin',
    '~/.config/composer/vendor/bin', '~/.composer/vendor/bin',
    '~/.dotnet/tools', '~/.krew/bin', '~/.local/share/pnpm', '~/.ghcup/bin',
    '~/.cabal/bin', '~/.juliaup/bin', '~/.opam/default/bin',
    '~/.nix-profile/bin', '~/.fly/bin', '~/.poetry/bin', '~/.pub-cache/bin',
    '~/.foundry/bin', '~/.sdkman/candidates/*/current/bin',
    '~/Library/Python/*/bin', '~/.emacs.d/bin', '~/.config/emacs/bin',
    '~/.local/share/flatpak/exports/bin',
    '/usr/local/bin', '/usr/local/sbin', '/usr/sbin', '/sbin', '/usr/local/go/bin',
    '/opt/homebrew/bin', '/opt/homebrew/sbin', '/home/linuxbrew/.linuxbrew/bin',
    '/opt/local/bin', '/snap/bin', '/var/lib/flatpak/exports/bin',
    '/nix/var/nix/profiles/default/bin', '/run/current-system/sw/bin',
    '/usr/lib/go/bin', '/usr/games', '/opt/*/bin',
)

# Where a project keeps the programs it installed for itself, relative to the
# project. Looked for in the working directory and its parents, up to the
# repository root.
PROJECT = (
    'node_modules/.bin', '.venv/bin', 'venv/bin', 'env/bin', '.env/bin',
    '.venv/Scripts', 'venv/Scripts', 'vendor/bin', 'bin', 'target/debug',
    'target/release', '.bundle/bin',
)
PROJECT_DEPTH = 4

NOT_FOUND = ('not found', 'unknown command', 'is not recognized as')


def _executable_in(directory, name):
    """The runnable file for `name` in `directory`, or None."""
    names = [name]
    if os.name == 'nt':
        source = os.environ.get('PATHEXT') or '.COM;.EXE;.BAT;.CMD'
        names += [name + extension for extension in source.split(';')
                  if extension]
    for candidate in names:
        path = os.path.join(directory, candidate)
        try:
            if (os.path.isfile(path) and os.access(path, os.X_OK)):
                return _as_spelled_on_disk(directory, candidate)
        except OSError:
            continue
    return None


def _as_spelled_on_disk(directory, name):
    """`cargo.exe` as the file is called, not `cargo.EXE` as PATHEXT spells
    the extension: this goes on the user's command line."""
    path = os.path.join(directory, name)
    if os.name != 'nt':
        return path
    try:
        for entry in os.listdir(directory):
            if entry.lower() == name.lower():
                return os.path.join(directory, entry)
    except OSError:
        pass
    return path


def _home_directories():
    import glob

    home = os.path.expanduser('~')
    if home == '~':
        return []
    found = []
    for pattern in HOMES:
        if pattern.startswith('~/'):
            # Joined piece by piece, so the separators are the platform's
            # own and not a mix of `/` from here and `\\` from `os.path`.
            pattern = os.path.join(home, *pattern[2:].split('/'))
        matches = sorted(glob.glob(pattern)) if '*' in pattern else [pattern]
        for directory in matches:
            if os.path.isdir(directory):
                found.append(directory)
    return found


def _project_directories(cwd):
    """Project bin directories from `cwd` upwards, nearest first."""
    found = []
    directory = cwd
    for _ in range(PROJECT_DEPTH):
        for relative in PROJECT:
            candidate = os.path.join(directory, *relative.split('/'))
            if os.path.isdir(candidate):
                found.append((candidate, directory))
        if os.path.exists(os.path.join(directory, '.git')):
            break
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return found


def _on_path(directory):
    for entry in os.environ.get('PATH', '').split(os.pathsep):
        if entry and os.path.normcase(os.path.abspath(entry)) == \
                os.path.normcase(os.path.abspath(directory)):
            return True
    return False


def _missing_program(command):
    """The typed program that is nowhere on PATH, or None."""
    parts = command.script_parts
    if not parts:
        return None
    start = command_word_index(parts)
    if start >= len(parts):
        return None
    word = parts[start]
    if not word or '/' in word or '\\' in word or word.startswith(('$', '~', '-')):
        return None
    if command.output is not None:
        lowered = command.output.lower()
        if word not in command.output or not any(
                marker in lowered for marker in NOT_FOUND):
            return None
    if which(word):
        return None
    return word


def match(command):
    return _missing_program(command) is not None


def _found(word):
    """Where `word` is, as `(path, directory, how)` pairs, best first."""
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = None

    places = []
    if cwd:
        for directory, project in _project_directories(cwd):
            path = _executable_in(directory, word)
            if path:
                places.append((path, directory, 'project', project))
    for directory in _home_directories():
        if _on_path(directory):
            continue
        path = _executable_in(directory, word)
        if path:
            places.append((path, directory, 'home', None))
    return places


def _relative(path, cwd):
    """`./node_modules/.bin/prettier`, with forward slashes, from `cwd`."""
    relative = os.path.relpath(path, cwd).replace(os.sep, '/')
    if not relative.startswith(('./', '../', '/')):
        relative = './' + relative
    return relative


def get_new_command(command):
    word = _missing_program(command)
    if word is None:
        return []
    places = _found(word)
    if not places:
        return []

    try:
        cwd = os.getcwd()
    except OSError:
        cwd = None

    parts = command.script_parts
    start = command_word_index(parts)
    rest = command.script[len(' '.join(parts[:start + 1])):] \
        if command.script.startswith(' '.join(parts[:start + 1])) else \
        ' ' + ' '.join(parts[start + 1:])
    lead = command.script[:len(' '.join(parts[:start]))] if start else ''
    if lead:
        lead += ' '

    suggestions = []
    for path, directory, how, project in places[:2]:
        if how == 'project' and cwd:
            shown = _relative(path, cwd)
            evidence = u'{} is in this project at {}'.format(word, shown)
        else:
            shown = path
            evidence = u'{} is installed at {}, which is not on PATH'.format(
                word, path)
        suggestions.append(Suggestion(
            lead + shell.quote(shown) + rest, confidence=0.9,
            evidence=(evidence,)))
        if how == 'home':
            suggestions.append(Suggestion(
                shell.and_(shell.put_on_path(directory), command.script),
                confidence=0.85,
                evidence=(evidence, u'puts {} on PATH for this shell'.format(
                    directory))))
    return suggestions
