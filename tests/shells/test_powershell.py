# -*- coding: utf-8 -*-

import pytest
from thebleep.shells import Powershell


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestPowershell(object):
    @pytest.fixture
    def shell(self):
        return Powershell()

    @pytest.fixture(autouse=True)
    def Popen(self, mocker):
        mock = mocker.patch('thebleep.shells.powershell.Popen')
        return mock

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

    @pytest.mark.parametrize('side_effect, expected_version, call_args', [
        ([b'''Major  Minor  Build  Revision
-----  -----  -----  --------
5      1      17763  316     \n'''], 'PowerShell 5.1.17763.316', ['powershell.exe']),
        ([IOError, b'PowerShell 6.1.2\n'], 'PowerShell 6.1.2', ['powershell.exe', 'pwsh'])])
    def test_info(self, side_effect, expected_version, call_args, shell, Popen):
        Popen.return_value.stdout.read.side_effect = side_effect
        assert shell.info() == expected_version
        assert Popen.call_count == len(call_args)
        assert all([Popen.call_args_list[i][0][0][0] == call_arg for i, call_arg in enumerate(call_args)])

    def test_get_version_error(self, shell, Popen):
        Popen.return_value.stdout.read.side_effect = RuntimeError
        with pytest.raises(RuntimeError):
            shell._get_version()
        assert Popen.call_args[0][0] == ['powershell.exe', '$PSVersionTable.PSVersion']
