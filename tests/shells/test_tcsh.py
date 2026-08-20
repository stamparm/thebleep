# -*- coding: utf-8 -*-

import os
import pytest
from thebleep.shells.tcsh import Tcsh


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestTcsh(object):
    @pytest.fixture
    def shell(self):
        return Tcsh()

    @pytest.fixture(autouse=True)
    def Popen(self, mocker):
        mock = mocker.patch('thebleep.shells.tcsh.Popen')
        mock.return_value.stdout.read.return_value = (
            b'bleep\teval $(thebleep $(fc -ln -1))\n'
            b'l\tls -CF\n'
            b'la\tls -A\n'
            b'll\tls -alF')
        return mock

    @pytest.mark.parametrize('before, after', [
        ('pwd', 'pwd'),
        ('bleep', 'eval $(thebleep $(fc -ln -1))'),
        ('awk', 'awk'),
        ('ll', 'ls -alF')])
    def test_from_shell(self, before, after, shell):
        assert shell.from_shell(before) == after

    def test_to_shell(self, shell):
        assert shell.to_shell('pwd') == 'pwd'

    def test_and_(self, shell):
        assert shell.and_('ls', 'cd') == 'ls && cd'

    def test_or_(self, shell):
        assert shell.or_('ls', 'cd') == 'ls || cd'

    def test_get_aliases(self, shell):
        assert shell.get_aliases() == {'bleep': 'eval $(thebleep $(fc -ln -1))',
                                       'l': 'ls -CF',
                                       'la': 'ls -A',
                                       'll': 'ls -alF'}

    def test_app_alias(self, shell):
        assert 'setenv TB_SHELL tcsh' in shell.app_alias('bleep')
        assert 'alias bleep' in shell.app_alias('bleep')
        assert 'alias BLEEP' in shell.app_alias('BLEEP')
        assert 'thebleep' in shell.app_alias('bleep')

    def test_app_alias_loader(self, shell):
        """tcsh cannot have a loader, so the flag gives it the real alias.

        A loader is a stub that calls itself once it has replaced itself. tcsh
        expands an alias when it *parses* the line, so the self-reference is
        expanded before the `eval` meant to redefine it runs, and tcsh answers
        `Alias loop.` -- every time, for as long as that line is in the
        `.cshrc`. It was the documented way to install for tcsh and it had
        never worked once. Verified against tcsh 6.24.

        """
        loader = shell.app_alias_loader('bleep')
        assert loader.startswith('alias bleep ')
        assert loader == shell.app_alias('bleep')

        # The self-reference is the loop, so its absence is the fix.
        assert '&& bleep \\!*' not in loader

    def test_get_history(self, history_lines, shell):
        history_lines(['ls', 'rm'])
        assert list(shell.get_history()) == ['ls', 'rm']

    def test_how_to_configure(self, shell, config_exists):
        config_exists.return_value = True
        assert shell.how_to_configure().can_configure_automatically

    def test_how_to_configure_when_config_not_found(self, shell,
                                                    config_exists):
        config_exists.return_value = False
        assert not shell.how_to_configure().can_configure_automatically

    @pytest.mark.parametrize('present, path', [
        (('.tcshrc',), '~/.tcshrc'),
        (('.cshrc',), '~/.cshrc'),
        (('.tcshrc', '.cshrc'), '~/.tcshrc'),
        ((), '~/.cshrc'),
    ])
    def test_which_startup_file_it_names(self, shell, config_exists,
                                         monkeypatch, present, path):
        """tcsh's own rule: `~/.tcshrc` when there is one, `~/.cshrc` otherwise.

        This said `~/.tcshrc` always, the installer said `~/.cshrc` always and
        the README said the rule -- so on the usual machine, which has a
        `.cshrc` and no `.tcshrc`, `--doctor` looked in a file the shell does
        not read and reported the alias missing from it.

        """
        config_exists.return_value = True
        home = os.path.expanduser('~')
        monkeypatch.setattr(
            'os.path.exists',
            lambda candidate: os.path.basename(candidate) in present
            and os.path.dirname(candidate) == home)
        assert shell.how_to_configure().path == path

    def test_info(self, shell, Popen):
        Popen.return_value.stdout.read.side_effect = [
            b'tcsh 6.20.00 (Astron) 2016-11-24 (unknown-unknown-bsd44) \n']
        assert shell.info() == 'Tcsh 6.20.00'
        assert Popen.call_args[0][0] == ['tcsh', '--version']

    @pytest.mark.parametrize('side_effect, exception', [
        ([b'\n'], IndexError), (OSError, OSError)])
    def test_get_version_error(self, side_effect, exception, shell, Popen):
        Popen.return_value.stdout.read.side_effect = side_effect
        with pytest.raises(exception):
            shell._get_version()
        assert Popen.call_args[0][0] == ['tcsh', '--version']
