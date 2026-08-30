import pytest
from tests.functional.plots import with_confirmation, without_confirmation, \
    refuse_with_confirmation, select_command_with_arrows

containers = ((u'thebleep/python3', u'', u'fish'),)


@pytest.fixture(params=containers)
def proc(request, spawnu, TIMEOUT):
    proc = spawnu(*request.param)
    proc.sendline(u'thebleep --alias > ~/.config/fish/config.fish')
    proc.sendline(u'fish')
    return proc


@pytest.fixture
def instant_proc(spawnu, TIMEOUT):
    proc = spawnu(u'thebleep/python3', u'', u'fish')
    proc.sendline(u'mkdir -p ~/.config/fish')
    proc.sendline(
        u"printf 'set -gx SHELL /usr/bin/fish\\n"
        u"eval (thebleep --alias --enable-experimental-instant-mode | "
        u"string collect)\\n' > ~/.config/fish/config.fish")
    proc.sendline(u'set -gx SHELL /usr/bin/fish')
    proc.sendline(
        u'eval (thebleep --alias --enable-experimental-instant-mode | '
        u'string collect)')
    # The setup starts a nested Fish under the logger. Its prompt carries this
    # marker; wait for that rather than a generic `# `, which also occurs in
    # the outer shell's earlier prompt.
    assert proc.expect([TIMEOUT, u'\u200b' * 10])
    proc.sendline(u'echo "instant mode ready: $THEBLEEP_INSTANT_MODE"')
    assert proc.expect([TIMEOUT, u'instant mode ready: True'])
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


@pytest.mark.functional
def test_instant_mode_uses_fish_capture_without_replay(instant_proc, TIMEOUT):
    refuse_with_confirmation(instant_proc, TIMEOUT)

# TODO: ensure that history changes.
