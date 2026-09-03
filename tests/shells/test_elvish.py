# -*- coding: utf-8 -*-

"""Elvish, against what 0.21 does."""

import os
import pytest
from thebleep.const import EXIT_EDIT
from thebleep.shells.elvish import Elvish


@pytest.mark.usefixtures('no_memoize', 'no_cache')
class TestElvish(object):
    @pytest.fixture
    def shell(self):
        return Elvish()

    @pytest.fixture(autouse=True)
    def version(self, mocker):
        return mocker.patch('thebleep.shells.elvish.tool_output',
                            return_value='0.21.0+Debian-2+b7\n')

    def test_the_alias_is_a_function(self, shell):
        alias = shell.app_alias('bleep')
        assert 'fn bleep {|@args|' in alias
        # The newest history entry is the function's own line.
        assert 'edit:command-history &newest-first | take 2 | drop 1' in alias
        assert 'TB_SHELL=elvish TB_ALIAS=bleep TB_CAN_EDIT=1' in alias
        assert 'if (eq $status {}) {{'.format(EXIT_EDIT) in alias
        assert 'set edit:current-command = $fixed' in alias
        assert 'eval $fixed' in alias
        assert shell.app_alias_loader('bleep') == alias

    @pytest.mark.parametrize('value, quoted', [
        ('plain', 'plain'),
        ('--short', '--short'),
        ('two words', "'two words'"),
        ("it's", "'it''s'"),
        ('~/x', "'~/x'"),
        ('$var', "'$var'"),
        ('a*b', "'a*b'"),
    ])
    def test_quote(self, shell, value, quoted):
        assert shell.quote(value) == quoted

    def test_and_is_a_semicolon(self, shell):
        assert shell.and_('cd x', 'ls') == 'cd x; ls'

    def test_or_is_try_catch(self, shell):
        assert shell.or_('a', 'b') == 'try { a } catch { b }'
        assert shell.or_('a', 'b', 'c') == 'try { a } catch { try { b } catch { c } }'

    def test_put_on_path(self, shell):
        assert shell.put_on_path('/opt/x/bin') == 'set paths = [/opt/x/bin $@paths]'
        assert shell.put_on_path('/opt/my tools') == \
            "set paths = ['/opt/my tools' $@paths]"

    def test_replay_argv(self, shell):
        assert shell.replay_argv('gti status') == (
            None if os.name == 'nt' else ['elvish', '-c', 'gti status'])

    def test_editing_is_offered(self, shell):
        assert shell.can_edit_buffer()

    def test_no_aliases_and_no_history(self, shell):
        assert shell.get_aliases() == {}
        assert shell.get_history() == []

    def test_version(self, shell):
        assert shell.info() == 'Elvish 0.21.0+Debian-2+b7'

    def test_how_to_configure(self, shell, tmp_path, monkeypatch):
        monkeypatch.setenv('HOME', str(tmp_path))
        monkeypatch.setenv('USERPROFILE', str(tmp_path))
        monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
        assert shell.how_to_configure().path == '~/.config/elvish/rc.elv'
