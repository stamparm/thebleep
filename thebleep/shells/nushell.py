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
from ..utils import DEVNULL, load_subprocess
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
            '        do --ignore-errors {{ ^thebleep $broken_command'
            ' {placeholder} ...$args }}\n'
            '    }} | default "")\n'
            '    if not ($fixed_command | is-empty) {{\n'
            '        commandline edit --replace $fixed_command\n'
            '    }}\n'
            '}}\n'
        ).format(name=alias_name, placeholder=ARGUMENT_PLACEHOLDER)

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

    def _config_dir(self):
        """Where Nushell keeps `config.nu` and, beside it, the history.

        Nushell asks the platform, so this does too: `%APPDATA%` on Windows,
        `~/Library/Application Support` on macOS, `$XDG_CONFIG_HOME` elsewhere.

        """
        if os.name == 'nt':
            base = os.environ.get('APPDATA') or os.path.expanduser('~')
        elif sys.platform == 'darwin':
            base = os.path.expanduser('~/Library/Application Support')
        else:
            base = (os.environ.get('XDG_CONFIG_HOME')
                    or os.path.expanduser('~/.config'))
        return os.path.join(base, 'nushell')

    def _get_history_file_name(self):
        """Whichever of the two formats is there.

        Nushell writes plain text or SQLite depending on
        `$env.config.history.file_format`, and the file that exists says which
        one this user chose.

        """
        directory = self._config_dir()
        plain = os.path.join(directory, 'history.txt')
        if os.path.isfile(plain):
            return plain
        return os.path.join(directory, 'history.sqlite3')

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
        import sqlite3
        from urllib.request import pathname2url

        from ..conf import settings

        query = 'SELECT command_line FROM history ORDER BY id'
        if settings.history_limit:
            query = ('SELECT command_line FROM ('
                     'SELECT id, command_line FROM history'
                     ' ORDER BY id DESC LIMIT {}) ORDER BY id'.format(
                         int(settings.history_limit)))
        try:
            connection = sqlite3.connect(
                'file:{}?mode=ro'.format(pathname2url(path)), uri=True)
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
        path = os.path.join(self._config_dir(), 'config.nu')
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
