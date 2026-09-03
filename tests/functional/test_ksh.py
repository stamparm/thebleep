import pytest
from tests.functional.plots import with_confirmation, without_confirmation, \
    refuse_with_confirmation, select_command_with_arrows

# Debian's ksh93u+m installs as `ksh93`; mksh is `mksh`. Both are Korn shells
# and both go through the one driver.
containers = ((u'thebleep/python3', u'', u'mksh'),
              (u'thebleep/python3', u'', u'ksh93'))


@pytest.fixture(params=containers)
def proc(request, spawnu, TIMEOUT):
    proc = spawnu(*request.param)
    proc.sendline(request.param[2])
    proc.sendline(u'export PYTHONIOENCODING=utf8')
    proc.sendline(u'eval "$(thebleep --alias)"')
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
