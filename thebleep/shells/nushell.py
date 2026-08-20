"""Nushell.

Nushell is different from the other shells here in one way that decides the
whole design: it has no `eval`. That is deliberate -- Nushell parses a script
completely before running any of it, which is where most of what it can tell you
about your pipeline comes from, and a string that turns into code at run time
cannot be parsed that way. There is no supported way to run a command written by
another program in the session you are sitting in.

`nu -c '...'` is not that. It starts a second Nushell, so `cd`, `$env` changes,
aliases and definitions all happen to a process that then exits -- and a good
share of what gets corrected is exactly that: `cd`, `mkdir -p x; cd x`,
`export`. A correction that silently did nothing would be worse than none.

So on Nushell a correction is written into your command line instead, with
`commandline edit --replace`, and you press return to run it yourself in your
own session. That is not a workaround for the missing `eval`; it is the same
thing the other shells do for `tab`, made the ordinary path here. Nothing is
run that you did not submit.

"""

import os
import re
import sys
from ..const import ARGUMENT_PLACEHOLDER, get_alias
from ..utils import DEVNULL, load_subprocess, memoize
from .generic import Generic, ShellConfiguration


# Bound the first time a process is started here; see `utils.load_subprocess`.
Popen = None
PIPE = None

# What `commandline edit --replace` needs. It was `commandline --replace` until
# Nushell 0.87 moved it under a subcommand.
MINIMUM_VERSION = (0, 87)

# Nushell's own commands, for telling a history line that would run something
# from one that would not. The first word is all that is ever looked at, so the
# subcommands (`str trim`, `path join`) are covered by their first word.
BUILTINS = [
    'alias', 'all', 'ansi', 'any', 'append', 'ast', 'bits', 'break', 'bytes',
    'cal', 'cd', 'char', 'chunks', 'clear', 'collect', 'columns', 'commandline',
    'compact', 'complete', 'config', 'const', 'continue', 'cp', 'date',
    'debug', 'decode', 'def', 'default', 'describe', 'detect', 'do', 'drop',
    'du', 'each', 'echo', 'encode', 'enumerate', 'error', 'every', 'exec',
    'exit', 'explain', 'explore', 'export', 'fill', 'filter', 'find', 'first',
    'flatten', 'for', 'format', 'from', 'generate', 'get', 'glob', 'grid',
    'group-by', 'hash', 'headers', 'help', 'hide', 'histogram', 'history',
    'http', 'if', 'ignore', 'input', 'insert', 'inspect', 'interleave', 'into',
    'is-admin', 'is-empty', 'is-not-empty', 'is-terminal', 'items', 'join',
    'keybindings', 'kill', 'last', 'length', 'let', 'lines', 'load-env', 'loop',
    'ls', 'match', 'math', 'merge', 'metadata', 'mkdir', 'mktemp', 'module',
    'move', 'mut', 'mv', 'nu-check', 'nu-highlight', 'open', 'overlay',
    'par-each', 'parse', 'path', 'plugin', 'port', 'prepend', 'print', 'ps',
    'query', 'random', 'reduce', 'reject', 'rename', 'return', 'reverse', 'rm',
    'roll', 'rotate', 'run-external', 'save', 'schema', 'scope', 'select',
    'seq', 'shuffle', 'skip', 'sleep', 'slice', 'sort', 'sort-by', 'split',
    'start', 'stor', 'str', 'sys', 'table', 'take', 'tee', 'term', 'timeit',
    'to', 'touch', 'transpose', 'try', 'ulimit', 'uname', 'uniq', 'uniq-by',
    'update', 'upsert', 'url', 'use', 'values', 'version', 'view', 'watch',
    'where', 'which', 'while', 'whoami', 'window', 'with-env', 'wrap', 'zip',
]

# What can be written as a bare word. The same set `shlex.quote` leaves alone,
# which is a subset of what Nushell would accept -- every one of Nushell's own
# metacharacters (`$ ( ) { } [ ] | ; # * ? ^ & < > !`, quotes, space) is outside
# it, so anything holding one gets quoted.
UNSAFE = re.compile(r'[^\w@%+=:,./-]', re.ASCII)


def _expanded(path):
    """`path` with a leading `~` expanded, or `None` if it could not be.

    `os.path.expanduser` hands the `~` straight back rather than raising when it
    cannot work out where home is -- which on POSIX effectively never happens,
    because the password database answers even with `HOME` unset, and on Windows
    happens whenever `USERPROFILE`, `HOME` and `HOMEDRIVE` are all absent: a
    service account, a stripped container, a test that cleared the environment.
    See `thebleep.system.paths` for the longer version.

    What comes back then is a path that does not exist and cannot be created,
    and the honest answer is not to name it at all.

    """
    expanded = os.path.expanduser(path)
    return None if expanded.startswith('~') else expanded


def _read_only_uri(path):
    """`path` as a SQLite URI that cannot create or modify the database.

    `mode=ro` so that reading somebody's history never creates one where there
    was none and never disturbs the shell that is writing it.

    The path is percent-encoded because a URI is not a path: `?` would start the
    query, `#` a fragment, and a space is not allowed. `/` and `:` are left
    alone, or `C:/Users/...` on Windows would stop naming a drive.

    """
    from urllib.parse import quote

    return 'file:{}?mode=ro'.format(
        quote(path.replace(os.sep, '/'), safe='/:'))


class Nushell(Generic):
    friendly_name = 'Nushell'

    def _shell_name(self):
        return 'nu'

    def app_alias(self, alias_name):
        """A command that puts the correction in the line editor.

        `do --ignore-errors` so that the exit status of a correction that found
        nothing is not an error in the caller's session, and without `complete`
        so that stderr still reaches the terminal -- the suggestion and the
        prompt that asks about it are written there, and the keys answering it
        are read from the terminal too.

        """
        return (
            'def {name} [...args] {{\n'
            '    let broken_command = (try {{'
            ' history | last 1 | get command | get 0 }} catch {{ "" }})\n'
            '    let fixed_command = (with-env {{TB_SHELL: "nu",'
            ' TB_ALIAS: "{name}"}} {{\n'
            '        do --ignore-errors {{ ^{command} $broken_command'
            ' {placeholder} ...$args }}\n'
            '    }} | default "")\n'
            '    if not ($fixed_command | is-empty) {{\n'
            '        commandline edit --replace $fixed_command\n'
            '    }}\n'
            '}}\n'
        ).format(name=alias_name, placeholder=ARGUMENT_PLACEHOLDER,
                 command=self._invocation())

    def app_alias_loader(self, alias_name):
        """The same thing, for the same reason there is no `eval`.

        Everywhere else the loader is a stub that asks `thebleep --alias` for
        the real definition the first time it is called, so that opening a shell
        runs no Python. Nushell cannot define a command from a string, so the
        definition has to be in the config file -- which costs nothing at
        startup anyway, because it is a dozen lines for Nushell to parse rather
        than an interpreter to start.

        """
        return self.app_alias(alias_name)

    def can_run_corrections(self):
        """No: see the note at the top of this module."""
        return False

    def can_edit_buffer(self):
        return True

    def and_(self, *commands):
        """Runs each command only if the one before it succeeded.

        Nushell has no `&&`. It had one until 0.60, when it became the boolean
        operator it is spelled like in every other language -- which is why
        `and`/`or` are the wrong thing to build a command chain out of here, and
        why a patch that used them chained booleans instead of commands.

        A failing command raises, and `try` stops the block at the one that
        raised, which is what `&&` means.

        """
        if len(commands) == 1:
            return commands[0]
        return u'try {{ {} }}'.format(u'; '.join(commands))

    def or_(self, *commands):
        """Runs each command only if the one before it failed."""
        if len(commands) == 1:
            return commands[0]
        first, rest = commands[0], commands[1:]
        return u'try {{ {} }} catch {{ {} }}'.format(first, self.or_(*rest))

    def mkdir_command(self):
        """Nushell's `mkdir` makes parents already and has no `-p`.

        Verified against nu 0.108: `mkdir -p x` is a parse error, "the mkdir
        command doesn't have flag -p", and `mkdir a/b/c` creates `a` and `b` on
        its own.

        """
        return u'mkdir'

    def quote(self, s):
        """A Nushell string literal for `s`.

        Not `shlex.quote`: POSIX escapes an embedded quote by leaving the
        single-quoted string and coming back into it, and a Nushell
        single-quoted string is literal all the way through with no way out, so
        that would produce three words. Anything holding a quote is written as a
        double-quoted string instead, which is the form that takes escapes.

        A bare `-something` would be read as a flag, so it is quoted even though
        every character in it is safe.

        """
        if not s:
            return u"''"
        if not UNSAFE.search(s) and s[0] not in u'-~':
            return s
        if u"'" not in s:
            return u"'{}'".format(s)
        return u'"{}"'.format(
            s.replace(u'\\', u'\\\\').replace(u'"', u'\\"'))

    def _config_dirs(self):
        """Everywhere Nushell might keep `config.nu` and, beside it, the history.

        `XDG_CONFIG_HOME` first, and on every platform rather than only on
        Linux: Nushell reads it before asking the platform, which `nu -c 'print
        $nu.default-config-dir'` confirms. Getting that order wrong is what sent
        this looking in `~/Library/Application Support` on a macOS machine whose
        Nushell was using the XDG directory.

        Then the platform's own answer, which is what Nushell falls back to:
        `%APPDATA%` on Windows, `~/Library/Application Support` on macOS,
        `~/.config` elsewhere. And on macOS `~/.config` as well, because which of
        the two a given Nushell build uses is a question this does not have to
        answer -- it can look in both and take the one that is there.

        """
        bases = []
        xdg = os.environ.get('XDG_CONFIG_HOME')
        if xdg:
            bases.append(xdg)

        if os.name == 'nt':
            bases.append(os.environ.get('APPDATA')
                         or os.path.join('~', 'AppData', 'Roaming'))
        elif sys.platform == 'darwin':
            bases.append(os.path.join('~', 'Library', 'Application Support'))
            bases.append(os.path.join('~', '.config'))
        else:
            bases.append(os.path.join('~', '.config'))

        places = []
        for base in bases:
            place = _expanded(os.path.join(base, 'nushell'))
            if place is not None and place not in places:
                places.append(place)
        return places

    def _config_dir(self):
        """The one to tell somebody to edit, or `None`.

        The one they already have, when they have one. `None` when there is
        nowhere to name -- see `_expanded` -- because a path with an unexpanded
        `~` still in it is worse advice than telling them to ask Nushell.

        """
        places = self._config_dirs()
        for place in places:
            if os.path.isdir(place):
                return place
        return places[0] if places else None

    # The two shapes reedline writes, depending on
    # `$env.config.history.file_format`.
    HISTORY_FILES = ('history.txt', 'history.sqlite3')

    def _get_history_file_name(self):
        """Whichever history is there, and if several, the one being written.

        Switching `file_format` leaves the other file behind rather than
        removing it, so "the one that exists" is not enough to go on -- the
        newest is the one this shell is actually appending to.

        """
        found = []
        for directory in self._config_dirs():
            for name in self.HISTORY_FILES:
                candidate = os.path.join(directory, name)
                try:
                    found.append((os.stat(candidate).st_mtime_ns, candidate))
                except OSError:
                    continue

        if found:
            return max(found)[1]

        # None yet. Named in the format Nushell writes by default, in the
        # directory it would write it to, so that `get_history` looks in the
        # right place once there is something to find. With nowhere to name, the
        # empty string: `Generic._get_history_lines` asks `os.path.isfile` about
        # it, gets `False`, and there is simply no history.
        directory = self._config_dir()
        return os.path.join(directory, self.HISTORY_FILES[0]) if directory \
            else ''

    def _get_history_lines(self):
        name = self._get_history_file_name()
        if name.endswith('.sqlite3'):
            return self._history_from_sqlite(name)
        return super(Nushell, self)._get_history_lines()

    def _history_from_sqlite(self, path):
        """The commands out of reedline's history database.

        Read-only and through a URI, so that opening it cannot create one and a
        history that is being written to at the same moment is not disturbed.
        Anything at all going wrong here means no history, which is a thing two
        rules do without rather than a reason to lose the correction.

        """
        if not os.path.isfile(path):
            return []

        # Only a Nushell user with a SQLite history reaches this, so the module
        # arrives here rather than at the top of the file.
        #
        # `urllib.parse.quote` and not `urllib.request.pathname2url`, which is
        # the obvious name for this: `urllib.request` brings `http.client`,
        # `email`, `ssl` and `socket` with it, and on macOS it also imports
        # `_scproxy` to ask the system about proxies. That is a great deal of
        # machinery to percent-encode a file name with.
        import sqlite3

        from ..conf import settings

        query = 'SELECT command_line FROM history ORDER BY id'
        if settings.history_limit:
            query = ('SELECT command_line FROM ('
                     'SELECT id, command_line FROM history'
                     ' ORDER BY id DESC LIMIT {}) ORDER BY id'.format(
                         int(settings.history_limit)))
        try:
            connection = sqlite3.connect(_read_only_uri(path), uri=True)
            try:
                return [line.strip() for (line,) in connection.execute(query)
                        if line and line.strip()]
            finally:
                connection.close()
        except Exception:
            from .. import logs

            logs.debug(u'Could not read the Nushell history at {}'.format(path))
            return []

    def _get_history_line(self, command_script):
        return u'{}\n'.format(command_script)

    def get_builtin_commands(self):
        return list(BUILTINS)

    def how_to_configure(self):
        """Where to put the alias, and whether we can put it there.

        With nowhere resolvable to name -- no `APPDATA` and no home directory
        Windows will admit to -- the advice is to ask Nushell, which knows: a
        path with an unexpanded `~` in it is not somewhere anybody can edit.

        """
        directory = self._config_dir()
        if directory is None:
            return ShellConfiguration(
                content=self.app_alias(get_alias()),
                path='($nu.default-config-dir | path join "config.nu")',
                reload='exec nu',
                can_configure_automatically=False)

        path = os.path.join(directory, 'config.nu')
        return ShellConfiguration(
            content=self.app_alias(get_alias()),
            path=path,
            reload='exec nu',
            can_configure_automatically=os.path.isfile(path))

    def _get_version(self):
        """Returns the version of the current shell"""
        Popen, PIPE = load_subprocess(globals())
        proc = Popen(['nu', '--version'], stdout=PIPE, stderr=DEVNULL)
        return proc.stdout.read().decode('utf-8').strip()

    @memoize
    def _version_pair(self):
        """`(major, minor)` from `nu --version`, or `None` if it could not ask.

        Memoized because starting Nushell to ask costs more than everything else
        `--doctor` does put together, and two checks want the answer.

        """
        try:
            version = self._get_version()
        except Exception:
            return None
        match = re.match(r'\s*(\d+)\.(\d+)', version)
        return (int(match.group(1)), int(match.group(2))) if match else None

    def unsupported_version(self):
        """Nushell before `commandline edit`, which is the whole integration.

        A correction here is written into the command line and nowhere else, so
        on a Nushell without `commandline edit --replace` there is no correction
        at all -- and the way that failed was a Nushell parse error out of the
        alias, several steps away from the thing that was wrong. `0.87` is where
        the subcommand arrived; before it the spelling was `commandline
        --replace`, and rather than writing both this says so.

        A version it could not read is not reported as too old: `nu` not being on
        `PATH` is an ordinary thing for a machine that is configured for Nushell
        and running something else at the moment.

        """
        version = self._version_pair()
        if version is None or version >= MINIMUM_VERSION:
            return None
        return 'Nushell {}.{} is older than {}.{}, where `commandline edit`' \
               ' arrived. A correction has no way to reach your command line' \
               ' before that, so it would not appear at all.'.format(
                   version[0], version[1], *MINIMUM_VERSION)
