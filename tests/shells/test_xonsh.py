# -*- coding: utf-8 -*-

"""xonsh, against what 0.19.4 does."""

import json
import os
import pytest
from thebleep.shells.xonsh import Xonsh


@pytest.mark.usefixtures('no_memoize', 'no_cache')
class TestXonsh(object):
    @pytest.fixture
    def shell(self):
        return Xonsh()

    @pytest.fixture(autouse=True)
    def version(self, mocker):
        return mocker.patch('thebleep.shells.xonsh.tool_output',
                            return_value='xonsh/0.19.4\n')

    def test_the_alias_is_a_python_function(self, shell):
        alias = shell.app_alias('bleep')
        assert alias.startswith('def _thebleep_bleep(args, stdin=None):')
        assert alias.rstrip().endswith("aliases['bleep'] = _thebleep_bleep")
        # The previous command is the newest history entry: the alias's own
        # line has not been recorded when it runs.
        assert 'history[-1].cmd' in alias
        assert "env['TB_SHELL'] = 'xonsh'" in alias
        assert 'execx(fixed)' in alias
        assert shell.app_alias_loader('bleep') == alias

    def test_the_alias_compiles_as_python(self, shell):
        compile(shell.app_alias('bleep'), '<alias>', 'exec')

    def test_aliases_come_from_the_environment(self, shell, monkeypatch):
        monkeypatch.setenv('TB_SHELL_ALIASES', 'll=ls -l\ng=git\nbroken')
        assert shell.get_aliases() == {'ll': 'ls -l', 'g': 'git'}
        assert shell.from_shell('g status') == 'git status'

    def test_no_aliases_without_the_environment(self, shell, monkeypatch):
        monkeypatch.delenv('TB_SHELL_ALIASES', raising=False)
        assert shell.get_aliases() == {}

    def test_replay_argv(self, shell):
        assert shell.replay_argv('gti status') == (
            None if os.name == 'nt'
            else ['xonsh', '--no-rc', '-c', 'gti status'])

    def test_version(self, shell):
        assert shell._get_version() == '0.19.4'
        assert shell.info() == 'xonsh 0.19.4'

    def test_put_on_path(self, shell):
        assert shell.put_on_path('/opt/x/bin') == "$PATH.insert(0, '/opt/x/bin')"

    def test_history_is_read_from_the_session_files(self, shell, tmp_path,
                                                    monkeypatch):
        monkeypatch.setenv('XONSH_DATA_DIR', str(tmp_path))
        sessions = tmp_path / 'history_json'
        sessions.mkdir()
        older = sessions / 'xonsh-a.json'
        older.write_text(json.dumps({'cmds': [{'inp': 'echo one\n', 'rtn': 0},
                                              {'inp': 'gti status\n',
                                               'rtn': 127}]}))
        newer = sessions / 'xonsh-b.json'
        newer.write_text(json.dumps({'cmds': [{'inp': 'ls\n', 'rtn': 0}]}))
        os.utime(str(older), (1, 1))
        os.utime(str(newer), (2, 2))
        (sessions / 'xonsh-c.json').write_text('{"cmds": [')     # unfinished
        assert list(shell._get_history_lines()) == [
            'echo one', 'gti status', 'ls']
        assert shell._get_history_file_name().endswith('xonsh-c.json') or \
            shell._get_history_file_name().endswith('xonsh-b.json')

    def test_how_to_configure(self, shell, tmp_path, monkeypatch):
        # Both: `expanduser` reads USERPROFILE on Windows and HOME elsewhere.
        monkeypatch.setenv('HOME', str(tmp_path))
        monkeypatch.setenv('USERPROFILE', str(tmp_path))
        monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
        assert shell.how_to_configure().path == '~/.config/xonsh/rc.xsh'
        (tmp_path / '.xonshrc').write_text('')
        assert shell.how_to_configure().path == '~/.xonshrc'

    def test_no_inline_editing(self, shell):
        assert not shell.can_edit_buffer()
