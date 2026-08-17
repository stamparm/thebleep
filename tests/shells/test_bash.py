# -*- coding: utf-8 -*-

import os
import pytest
from thebleep.shells import Bash


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestBash(object):
    @pytest.fixture
    def shell(self):
        return Bash()

    @pytest.fixture(autouse=True)
    def Popen(self, mocker):
        mock = mocker.patch('thebleep.shells.bash.Popen')
        return mock

    @pytest.fixture(autouse=True)
    def shell_aliases(self):
        os.environ['TB_SHELL_ALIASES'] = (
            'alias bleep=\'eval $(thebleep $(fc -ln -1))\'\n'
            'alias l=\'ls -CF\'\n'
            'alias la=\'ls -A\'\n'
            'alias ll=\'ls -alF\'')

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

    @pytest.mark.parametrize('alias, parsed', [
        ('alias ll=\'ls -alF\'', ('ll', 'ls -alF')),
        ('alias empty=', ('empty', '')),
        ('alias quote=\'', ('quote', "'"))])
    def test_parse_alias(self, shell, alias, parsed):
        assert shell._parse_alias(alias) == parsed

    def test_app_alias(self, shell):
        assert 'bleep () {' in shell.app_alias('bleep')
        assert 'BLEEP () {' in shell.app_alias('BLEEP')
        assert 'thebleep' in shell.app_alias('bleep')
        assert 'PYTHONIOENCODING' in shell.app_alias('bleep')

    def test_app_alias_loader(self, shell):
        loader = shell.app_alias_loader('bleep')
        assert 'bleep() {' in loader
        assert 'thebleep --alias bleep' in loader
        assert 'bleep "$@"' in loader

    def test_app_alias_variables_correctly_set(self, shell):
        alias = shell.app_alias('bleep')
        assert "bleep () {" in alias
        assert 'TB_SHELL=bash' in alias
        assert "TB_ALIAS=bleep" in alias
        assert 'PYTHONIOENCODING=utf-8' in alias
        assert 'TB_SHELL_ALIASES=$(alias)' in alias

    def test_get_history(self, history_lines, shell):
        history_lines(['ls', 'rm'])
        assert list(shell.get_history()) == ['ls', 'rm']

    def test_split_command(self, shell):
        command = 'git log -p'
        command_parts = ['git', 'log', '-p']
        assert shell.split_command(command) == command_parts

    def test_how_to_configure(self, shell, config_exists):
        config_exists.return_value = True
        assert shell.how_to_configure().can_configure_automatically

    def test_how_to_configure_when_config_not_found(self, shell,
                                                    config_exists):
        config_exists.return_value = False
        assert not shell.how_to_configure().can_configure_automatically

    def test_info(self, shell, Popen):
        Popen.return_value.stdout.read.side_effect = [b'3.5.9']
        assert shell.info() == 'Bash 3.5.9'

    def test_get_version_error(self, shell, Popen):
        Popen.return_value.stdout.read.side_effect = OSError
        with pytest.raises(OSError):
            shell._get_version()
        assert Popen.call_args[0][0] == ['bash', '-c', 'echo $BASH_VERSION']
