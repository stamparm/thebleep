import pytest
from tests.functional.plots import with_confirmation, without_confirmation, \
    refuse_with_confirmation, select_command_with_arrows

containers = ((u'thebleep/python3', u'', u'bash'),)


@pytest.fixture(params=containers)
def proc(request, spawnu, TIMEOUT):
    proc = spawnu(*request.param)
    # Elvish's `eval` runs code in a namespace of its own, so a function
    # defined through it is gone when it returns; the alias goes where it goes
    # for everybody, into rc.elv, and the shell is started after.
    proc.sendline(u'mkdir -p ~/.config/elvish')
    proc.sendline(u'thebleep --shell elvish --alias > ~/.config/elvish/rc.elv')
    proc.sendline(u'export PYTHONIOENCODING=utf8')
    proc.sendline(u'elvish')
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
