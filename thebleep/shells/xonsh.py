# -*- encoding: utf-8 -*-

"""xonsh: the Python shell.

Everything about it is Python, so the alias is a Python function rather than
shell text. It reads the previous command from `__xonsh__.history` -- which,
inside an alias, has not yet recorded the alias's own line, so `[-1]` is the
command that failed -- passes it and the shell's aliases to The Bleep in the
environment, and runs what comes back with `execx`, which parses xonsh
syntax. Verified against xonsh 0.19.

The startup file is `~/.config/xonsh/rc.xsh`, or the older `~/.xonshrc`; the
alias text goes in as it is, since xonsh has no `eval "$(...)"` and no need
for a loader stub: defining a function costs nothing until it runs.

History lives in JSON files, one per session, under `$XONSH_DATA_DIR`; the
newest are read when a rule asks. Editing before running is not offered:
prompt_toolkit's buffer is not reachable from an alias.

"""

import glob
import json
import os

from ..const import get_alias
from ..utils import memoize, tool_output
from .generic import Generic


# The `--ambient` handler, as Python for xonsh to run. `__SOCK__` is the
# warm server's socket, or '' with `warm_server` off; `__WORDS__` the words
# that reach The Bleep.
AMBIENT = '''\
def _thebleep_ambient_install():
    import json, keyword, os, re, socket, subprocess, sys
    sock = __SOCK__
    words = __WORDS__
    plain = re.compile(r'^[A-Za-z_][A-Za-z0-9_.+-]*$')
    python = re.compile(r"[=()\\[\\]{}'\\"`$@|;&<>\\\\]|(?:^|\\s)(?:[-+*/%]+|==|!=|<=|>=|in|is|not|and|or|if|else|for|lambda)(?:\\s|$)")
    last = {}

    def environment():
        env = dict(__xonsh__.env.detype())
        env['TB_SHELL'] = __SHELL__
        env['TB_SHELL_ALIASES'] = '\\n'.join(
            k + '=' + ' '.join(v) for k, v in aliases.items()
            if isinstance(v, list) and v)
        return env

    def directly(line):
        done = subprocess.run(words + ['--inline', '--command', line],
                              env=environment(), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        out = done.stdout.decode('utf-8', 'replace').strip()
        return out if done.returncode == 0 and out else None

    def start():
        subprocess.Popen(words + ['--serve'], env=environment(),
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)

    def ask(line, known):
        if not sock:
            return None if known else directly(line)
        if not os.path.exists(sock):
            start()
            return None if known else directly(line)
        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.settimeout(1)
            connection.connect(sock)
            env = environment()
            connection.sendall(json.dumps({
                'script': line, 'aliases': env['TB_SHELL_ALIASES'],
                'cwd': os.getcwd(), 'path': env.get('PATH', ''),
                'known': known}).encode('utf-8') + b'\\n')
            data = b''.join(iter(lambda: connection.recv(65536), b''))
            connection.close()
        except OSError as error:
            # Refused: a socket left by a server that was killed.
            if isinstance(error, ConnectionRefusedError):
                start()
            return None if known else directly(line)
        status, _, body = data.partition(b'\\n')
        if status == b'ok' and body:
            return body.decode('utf-8', 'replace')
        if status == b'none':
            return None
        return None if known else directly(line)

    def runnable(word):
        return (keyword.iskeyword(word) or word in __xonsh__.ctx
                or hasattr(__builtins__, word) or (
                    isinstance(__builtins__, dict) and word in __builtins__)
                or word in aliases or word in __xonsh__.commands_cache)

    @events.on_transform_command
    def _thebleep_ambient(cmd, **kw):
        # Fired more than once per line, by design: answer the same way.
        if last.get('cmd') == cmd:
            return last['result']
        result = cmd
        line = cmd.strip()
        parts = line.split()
        if parts and '\\n' not in line and not python.search(line) \\
                and plain.match(parts[0]):
            first = parts[0]
            second = parts[1] if len(parts) > 1 else ''
            fixed = what = None
            if not runnable(first):
                fixed = ask(line, False)
                what = first + ' is not a command'
            elif second and plain.match(second) and first not in aliases \\
                    and first in __xonsh__.commands_cache:
                fixed = ask(line, True)
                what = second + ' is not a ' + first + ' command'
            if fixed and fixed != line:
                print('bleep: ' + what + '; return runs `' + fixed + '`',
                      file=sys.stderr)
                if __xonsh__.env.get_docs('XONSH_PROMPT_NEXT_CMD').doc:
                    __xonsh__.env['XONSH_PROMPT_NEXT_CMD'] = fixed
                result = ''
        last['cmd'], last['result'] = cmd, result
        return result

_thebleep_ambient_install()
del _thebleep_ambient_install
'''


class Xonsh(Generic):
    friendly_name = 'xonsh'

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv(['xonsh', '--no-rc', '-c', script])

    def quote(self, s):
        """An argument xonsh passes through exactly as `s`.

        Not `shlex.quote`: xonsh reads a backslash inside single quotes as an
        escape, so `'a\\' '` closes nowhere near where POSIX says, and it
        expands `$HOME` and `~` inside quotes too. `@(...)` is a Python
        expression whose value is the argument, and a Python literal of `s`
        is `s` with nothing expanded. A word with nothing special in it is
        left bare, as everywhere else.

        """
        from shlex import quote

        if s and quote(s) == s:
            return s
        return u'@({!r})'.format(s)

    def app_alias(self, alias_name):
        # Written out as Python, so nothing here is shell-quoted; the
        # invocation's words are repr'd into a list for `subprocess.run`.
        from .. import invocation

        override = invocation.override()
        if override:
            words = ['sh', '-c', override + ' "$@"', 'thebleep']
        else:
            words = invocation.parts() or [invocation.ENTRY_POINT]
        return '''\
def _thebleep_{name}(args, stdin=None):
    import os, subprocess
    history = __xonsh__.history
    last = history[-1].cmd.strip() if len(history) else ''
    env = dict(__xonsh__.env.detype())
    env['TB_ALIAS'] = {name!r}
    env['TB_SHELL'] = 'xonsh'
    env['TB_EXIT'] = str(history[-1].rtn if len(history) else 0)
    env['TB_SHELL_ALIASES'] = '\\n'.join(
        k + '=' + ' '.join(v) for k, v in aliases.items()
        if isinstance(v, list) and v)
    fixed = subprocess.run({words!r} + [last], env=env,
                           stdout=subprocess.PIPE).stdout.decode()
    if fixed.strip():
        execx(fixed)

aliases[{name!r}] = _thebleep_{name}'''.format(name=alias_name, words=words)

    def app_alias_loader(self, alias_name):
        # The alias itself: a function definition is already the cheap thing
        # a loader stub would stand in for.
        return self.app_alias(alias_name)

    def ambient_binding(self):
        """Correct a misspelled program before it runs, in Python.

        xonsh fires `on_transform_command` with the line as it was accepted
        and runs whatever the handler returns, which is the hook the other
        shells' return bindings stand in for. The handler asks the same two
        questions zsh asks -- is the first word something the shell can run
        (a command, an alias, a keyword, a builtin or a name in the
        session), and if it is a command, is the word after it one the
        program has (`thebleep.ambient`) -- and on a fix returns nothing to
        run, prints the message, and puts the fix in
        `$XONSH_PROMPT_NEXT_CMD`, which is what the next prompt opens with.
        So nothing runs, the corrected line is there, and return runs it:
        the same shape as everywhere else. A xonsh without that variable
        gets the message alone.

        xonsh is Python, so it speaks to the warm server's socket itself,
        with no helper. A line with anything that could be Python in it --
        an operator, a bracket, a quote, an assignment -- is left alone.

        """
        from .. import invocation
        from ..conf import settings
        from ..serve import socket_path

        override = invocation.override()
        if override:
            words = ['sh', '-c', override + ' "$@"', 'thebleep']
        else:
            words = invocation.parts() or [invocation.ENTRY_POINT]
        return (AMBIENT.replace('__WORDS__', repr(words))
                .replace('__SOCK__', repr(socket_path('xonsh')
                                          if settings.warm_server else ''))
                .replace('__SHELL__', repr('xonsh')))

    @memoize
    def get_aliases(self):
        """From the environment the alias filled, `name=words` per line.

        Not by starting xonsh: that costs most of a second, and the alias
        already has the dictionary in hand when it runs.

        """
        listed = os.environ.get('TB_SHELL_ALIASES', '')
        aliases = {}
        for line in listed.splitlines():
            name, separator, value = line.partition('=')
            if separator and name:
                aliases[name] = value
        return aliases

    def _data_directory(self):
        named = os.environ.get('XONSH_DATA_DIR')
        if named:
            return named
        base = os.environ.get('XDG_DATA_HOME') or os.path.join(
            os.path.expanduser('~'), '.local', 'share')
        return os.path.join(base, 'xonsh')

    def _get_history_file_name(self):
        """The newest session file, for anything that asks for one path."""
        files = self._history_files()
        return files[-1] if files else ''

    def _history_files(self):
        pattern = os.path.join(self._data_directory(), 'history_json',
                               'xonsh-*.json')
        return sorted(glob.glob(pattern), key=os.path.getmtime)

    def _get_history_lines(self):
        """Commands from the most recent session files, oldest first.

        A session file is `{"cmds": [{"inp": ..., "rtn": ...}, ...]}` and a
        session still running has a file that is not finished; both parse
        or are skipped. Only as many files as it takes to fill
        `history_limit`, from the newest back.

        """
        from ..conf import settings

        wanted = settings.history_limit or 1000
        collected = []
        for path in reversed(self._history_files()):
            try:
                with open(path, 'rb') as handle:
                    entries = json.load(handle).get('cmds', [])
            except (OSError, ValueError, AttributeError):
                continue
            commands = [entry.get('inp', '').strip() for entry in entries
                        if isinstance(entry, dict)]
            collected = [command for command in commands if command] \
                + collected
            if len(collected) >= wanted:
                break
        for command in collected[-wanted:]:
            yield command

    def _get_history_line(self, command_script):
        # xonsh keeps its own JSON; nothing is appended by hand.
        return ''

    def put_on_path(self, directory):
        return u'$PATH.insert(0, {!r})'.format(directory)

    def how_to_configure(self):
        home = os.path.expanduser('~')
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.join(home, '.config')
        xdg = os.path.join(base, 'xonsh', 'rc.xsh')
        if os.path.exists(os.path.join(home, '.xonshrc')) \
                and not os.path.exists(xdg):
            config = '~/.xonshrc'
        else:
            # Forward slashes on every platform: a line for a person to read.
            config = xdg.replace(home, '~', 1).replace('\\', '/')
        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path=config,
            reload='xonsh')

    def _get_version(self):
        """`xonsh/0.19.4`, as `xonsh --version` prints it."""
        return tool_output(['xonsh', '--version']).strip().replace(
            'xonsh/', '')
