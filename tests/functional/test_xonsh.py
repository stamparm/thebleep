import pytest
from tests.functional.plots import with_confirmation, without_confirmation, \
    refuse_with_confirmation, select_command_with_arrows

containers = ((u'thebleep/python3', u'', u'bash'),)


@pytest.fixture(params=containers)
def proc(request, spawnu, TIMEOUT):
    proc = spawnu(*request.param)
    proc.sendline(u'xonsh --no-rc')
    # xonsh loses what is typed while it starts up and prints its welcome, so
    # nothing is sent until the banner has been seen and the prompt is up.
    assert proc.expect([TIMEOUT, u'Welcome to the xonsh shell'])
    assert proc.expect([TIMEOUT, u'install prompt_toolkit'])
    proc.sendline(u'')
    assert proc.expect([TIMEOUT, u'@#'])
    proc.sendline(u'$PYTHONIOENCODING = "utf8"')
    # `--alias` prints Python; `execx` runs it in this shell.
    proc.sendline(u'execx($(thebleep --alias))')
    return proc


@pytest.mark.functional
def test_with_confirmation(proc, TIMEOUT):
    with_confirmation(proc, TIMEOUT)


@pytest.mark.functional
def test_select_command_with_arrows(proc, TIMEOUT):
    select_command_with_arrows(proc, TIMEOUT)


@pytest.mark.functional
def test_refuse_with_confirmation(proc, TIMEOUT):
    refuse_with_confirmation(proc, TIMEOUT)


@pytest.mark.functional
def test_without_confirmation(proc, TIMEOUT):
    without_confirmation(proc, TIMEOUT)
