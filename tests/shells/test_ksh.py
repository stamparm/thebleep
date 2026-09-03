# -*- coding: utf-8 -*-

"""The Korn shells, with what ksh93u+m 1.0.10 and mksh R59 actually print."""

import os
import pytest
from thebleep.shells.ksh import Ksh, PROGRAMS


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestKsh(object):
    @pytest.fixture
    def shell(self, mocker):
        mocker.patch('thebleep.shells.ksh.which',
                     side_effect=lambda name: '/bin/mksh'
                     if name == 'mksh' else None)
        return Ksh()

    @pytest.fixture(autouse=True)
    def probes(self, mocker):
        # `mksh -ic alias`, verbatim, builtin aliases included.
        mocker.patch('thebleep.shells.ksh.tool_lines', return_value=[
            "autoload='\\\\builtin typeset -fu'",
            "bleep='eval \"$(TB_ALIAS=bleep thebleep \"$(fc -ln -1 -1)\")\"'",
            "l='ls -CF'",
            "ll='ls -alF'",
            "say='echo '\\''hi'\\'''",
            "type='\\\\builtin whence -v'"])
        return mocker.patch('thebleep.shells.ksh.tool_output',
                            return_value='@(#)MIRBSD KSH R59 2025/04/26\n')

    def test_the_program_is_the_one_on_path(self, shell):
        assert shell.program == 'mksh'
        assert shell._shell_name() == 'mksh'

    def test_the_alias_names_the_program_it_was_told(self, mocker, monkeypatch):
        monkeypatch.setenv('TB_SHELL', 'ksh93')
        mocker.patch('thebleep.shells.ksh.which',
                     side_effect=lambda name: '/usr/bin/' + name
                     if name in PROGRAMS else None)
        assert Ksh().program == 'ksh93'

    @pytest.mark.parametrize('before, after', [
        ('pwd', 'pwd'),
        ('ll', 'ls -alF'),
        ('say', "echo 'hi'"),
        ('awk', 'awk')])
    def test_from_shell(self, before, after, shell):
        assert shell.from_shell(before) == after

    def test_get_aliases(self, shell):
        aliases = shell.get_aliases()
        assert aliases['l'] == 'ls -CF'
        assert aliases['type'] == '\\\\builtin whence -v'
        assert aliases['say'] == "echo 'hi'"

    def test_app_alias(self, shell):
        alias = shell.app_alias('bleep')
        assert alias.startswith("alias bleep='")
        assert 'TB_SHELL=mksh' in alias
        # Both ends of the range: ksh93 has already recorded the alias's own
        # line when it runs, and an open range would end with `bleep`.
        assert 'fc -ln -1 -1' in alias
        assert 'thebleep' in alias

    def test_app_alias_loader_is_a_posix_function(self, shell):
        loader = shell.app_alias_loader('bleep')
        assert loader.startswith('bleep() {')
        assert 'TB_SHELL=mksh' in loader

    def test_replay_argv(self, shell):
        assert shell.replay_argv('gti status') == (
            None if os.name == 'nt' else ['mksh', '-c', 'gti status'])

    def test_and_or(self, shell):
        assert shell.and_('ls', 'cd') == 'ls && cd'
        assert shell.or_('ls', 'cd') == 'ls || cd'

    def test_version(self, shell):
        assert shell._get_version() == 'MIRBSD KSH R59 2025/04/26'
        assert shell.info() == 'mksh MIRBSD KSH R59 2025/04/26'

    def test_the_history_file_is_histfile_first(self, shell, monkeypatch):
        monkeypatch.setenv('HISTFILE', '/tmp/somewhere')
        assert shell._get_history_file_name() == '/tmp/somewhere'

    def test_the_history_file_defaults_to_ksh93s(
            self, shell, monkeypatch, mocker):
        monkeypatch.delenv('HISTFILE', raising=False)
        mocker.patch('os.path.isfile', return_value=False)
        assert shell._get_history_file_name().endswith('.sh_history')

    @pytest.mark.parametrize('framed', [
        # mksh: a header, then `\0\xff\0\0\0` and a counter before each entry.
        (b'\xab\xcd\xff\x00\x00\x00\x01alias l="ls -CF"\x00\xff\x00\x00\x00'
         b'\x02echo first\x00\xff\x00\x00\x00\x03gti status\x00\xff\x00\x00'
         b'\x00\x04bleep'),
        # ksh93: a two-byte header, `\n\0` after each entry.
        (b'\x81\x01alias l="ls -CF"\n\x00echo first\n\x00gti status\n\x00'
         b'bleep\n\x00'),
    ])
    def test_the_history_is_read_through_the_framing(self, shell, framed,
                                                     tmp_path, monkeypatch):
        path = tmp_path / 'hist'
        path.write_bytes(framed)
        monkeypatch.setenv('HISTFILE', str(path))
        assert list(shell._get_history_lines()) == [
            'alias l="ls -CF"', 'echo first', 'gti status', 'bleep']

    def test_a_unicode_command_survives_the_framing(self, shell, tmp_path,
                                                    monkeypatch):
        path = tmp_path / 'hist'
        path.write_bytes(b'\x81\x01echo \xc3\xbcber\n\x00')
        monkeypatch.setenv('HISTFILE', str(path))
        assert list(shell._get_history_lines()) == [u'echo \xfcber']

    def test_how_to_configure_prefers_env_then_the_shells_own(
            self, shell, monkeypatch, mocker):
        monkeypatch.delenv('ENV', raising=False)
        mocker.patch('os.path.exists', return_value=False)
        assert shell.how_to_configure().path == '~/.mkshrc'
        monkeypatch.setenv('ENV', os.path.expanduser('~/.kshrc'))
        assert shell.how_to_configure().path == '~/.kshrc'

    def test_no_inline_editing(self, shell):
        assert not shell.can_edit_buffer()
