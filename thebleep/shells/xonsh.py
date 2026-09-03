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


class Xonsh(Generic):
    friendly_name = 'xonsh'

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv(['xonsh', '--no-rc', '-c', script])

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
