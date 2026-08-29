# -*- coding: utf-8 -*-

import pytest
from thebleep.shells import Powershell


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestPowershell(object):
    @pytest.fixture
    def shell(self):
        return Powershell()

    @pytest.fixture(autouse=True)
    def probes(self, mocker):
        """What the two version probes said. See `test_bash`."""
        mocker.patch('thebleep.shells.powershell.tool_lines',
                     return_value=[])
        return mocker.patch('thebleep.shells.powershell.tool_output',
                            return_value='')

    def test_and_(self, shell):
        """`(a) -and (b)` was not `a && b`.

        `-and` is a boolean operator over expressions and `$(...)` captures
        output, so it tested whether the first command *printed* something: a
        command that succeeded quietly, like `git add .`, stopped the chain.
        `$?` is the exit status, and works in Windows PowerShell 5.1 as well as
        in 7, which `&&` does not.

        """
        assert shell.and_('ls') == 'ls'
        assert shell.and_('ls', 'cd') == 'ls; if ($?) { cd }'
        assert shell.and_('a', 'b', 'c') == 'a; if ($?) { b; if ($?) { c } }'
        assert shell.and_() == ''

    def test_or_(self, shell):
        assert shell.or_('ls', 'cd') == 'ls; if (-not $?) { cd }'
        assert shell.or_('a', 'b', 'c') == \
            'a; if (-not $?) { b; if (-not $?) { c } }'

    def test_split_command_ignores_call_operator(self, shell):
        assert shell.split_command("& 'C:/Program Files/tool' 'a b'") == \
            ['C:/Program Files/tool', 'a b']

    @pytest.mark.parametrize('value, quoted', [
        ('plain', "'plain'"),
        ('two words', "'two words'"),
        ("it's", "'it''s'"),
        ('$(Get-Date)', "'$(Get-Date)'"),
        ('a;b', "'a;b'"),
        ('a`b', "'a`b'"),
        ('a&b', "'a&b'"),
        (u'\u00fcnic\u00f8de', u"'\u00fcnic\u00f8de'"),
    ])
    def test_quote(self, shell, value, quoted):
        """PowerShell does not join adjacent string literals.

        `shlex.quote` escapes an embedded quote by leaving the single-quoted
        string and re-entering it, and a command then receives three arguments
        rather than one. A doubled quote is PowerShell's own way of writing it.

        """
        assert shell.quote(value) == quoted

    def test_app_alias(self, shell):
        assert 'function bleep' in shell.app_alias('bleep')
        assert 'function BLEEP' in shell.app_alias('BLEEP')
        assert 'thebleep' in shell.app_alias('bleep')

    def test_app_alias_loader(self, shell):
        loader = shell.app_alias_loader('bleep')
        assert 'function bleep {' in loader
        assert 'thebleep --alias bleep' in loader

    def test_how_to_configure(self, shell):
        assert not shell.how_to_configure().can_configure_automatically

    def test_info_from_windows_powershell(self, shell, mocker):
        mocker.patch('thebleep.shells.powershell.tool_lines', return_value=[
            'Major  Minor  Build  Revision',
            '-----  -----  -----  --------',
            '5      1      17763  316     '])
        assert shell.info() == 'PowerShell 5.1.17763.316'

    def test_info_falls_back_to_pwsh(self, shell, probes):
        """`powershell.exe` is not on a machine that only has PowerShell 7,
        and `tool_lines` reports that as no answer rather than as an
        `IOError` -- which is what this used to catch."""
        probes.return_value = 'PowerShell 6.1.2'
        assert shell.info() == 'PowerShell 6.1.2'
        assert probes.call_args[0][0] == ['pwsh', '--version']

    def test_neither_probe_answers(self, shell, probes):
        probes.return_value = ''
        assert shell.info() == 'PowerShell'
