# -*- coding: utf-8 -*-

import os
import pytest
from thebleep import const
from thebleep.shells.zsh import Zsh


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestZsh(object):
    @pytest.fixture
    def shell(self):
        return Zsh()

    @pytest.fixture(autouse=True)
    def probe(self, mocker):
        """What `zsh -c 'echo $ZSH_VERSION'` said. See `test_bash`."""
        return mocker.patch('thebleep.shells.zsh.tool_output',
                            return_value='')

    @pytest.fixture(autouse=True)
    def shell_aliases(self):
        os.environ['TB_SHELL_ALIASES'] = (
            'bleep=\'eval $(thebleep $(fc -ln -1 | tail -n 1))\'\n'
            'l=\'ls -CF\'\n'
            'la=\'ls -A\'\n'
            'll=\'ls -alF\'')

    @pytest.mark.parametrize('before, after', [
        ('bleep', 'eval $(thebleep $(fc -ln -1 | tail -n 1))'),
        ('pwd', 'pwd'),
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
        assert shell.get_aliases() == {
            'bleep': 'eval $(thebleep $(fc -ln -1 | tail -n 1))',
            'l': 'ls -CF',
            'la': 'ls -A',
            'll': 'ls -alF'}

    @pytest.mark.parametrize('alias, parsed', [
        ('ll=\'ls -alF\'', ('ll', 'ls -alF')),
        ('empty=', ('empty', '')),
        ('quote=\'', ('quote', "'"))])
    def test_parse_alias(self, shell, alias, parsed):
        assert shell._parse_alias(alias) == parsed

    def test_app_alias(self, shell):
        assert 'bleep () {' in shell.app_alias('bleep')
        assert 'BLEEP () {' in shell.app_alias('BLEEP')
        assert 'thebleep' in shell.app_alias('bleep')

    def test_app_alias_loader(self, shell):
        loader = shell.app_alias_loader('bleep')
        assert 'bleep() {' in loader
        assert 'thebleep --alias bleep' in loader

    def test_app_alias_variables_correctly_set(self, shell):
        alias = shell.app_alias('bleep')
        assert "bleep () {" in alias
        assert 'TB_SHELL=zsh' in alias
        assert "TB_ALIAS=bleep" in alias
        assert 'TB_SHELL_ALIASES=$(alias)' in alias

    def test_app_alias_can_edit(self, shell):
        alias = shell.app_alias('bleep')
        assert 'TB_CAN_EDIT=1' in alias
        # `-r`, or `print` would eat the backslashes in a correction.
        assert 'print -z -r -- "$TB_CMD"' in alias
        assert '-eq {}'.format(const.EXIT_EDIT) in alias

    def test_inline_binding_only_edits_zle(self, shell):
        binding = shell.inline_binding()
        assert "bindkey '\\e\\e'" in binding
        assert '--inline --command "$BUFFER"' in binding
        assert 'BUFFER=$fixed' in binding
        assert 'eval' not in binding

    def test_get_history(self, history_lines, shell):
        history_lines([': 1432613911:0;ls', ': 1432613916:0;rm'])
        assert list(shell.get_history()) == ['ls', 'rm']

    def test_how_to_configure(self, shell, config_exists):
        config_exists.return_value = True
        assert shell.how_to_configure().can_configure_automatically

    def test_how_to_configure_when_config_not_found(self, shell,
                                                    config_exists):
        config_exists.return_value = False
        assert not shell.how_to_configure().can_configure_automatically

    def test_info(self, shell, probe):
        probe.return_value = '3.5.9'
        assert shell.info() == 'ZSH 3.5.9'
        assert probe.call_args[0][0] == ['zsh', '-c', 'echo $ZSH_VERSION']

    def test_a_probe_that_answers_nothing(self, shell, probe):
        probe.return_value = ''
        assert shell.info() == 'ZSH'
