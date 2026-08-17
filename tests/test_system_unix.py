# -*- encoding: utf-8 -*-

import os
import pty
import pytest
import sys
import termios
import tty
from thefuck import const

pytestmark = pytest.mark.skipif(sys.platform == 'win32',
                                reason="skip when running on Windows")

if sys.platform != 'win32':
    from thefuck.system import unix


@pytest.fixture
def pressed(monkeypatch):
    """Feeds keys to a terminal `get_key` then reads from."""
    setraw = tty.setraw
    master, slave = pty.openpty()
    setraw(slave)
    monkeypatch.setattr('sys.stdin', os.fdopen(slave))
    # The default `TCSAFLUSH` would throw away what the test just typed.
    monkeypatch.setattr('tty.setraw',
                        lambda fd: setraw(fd, termios.TCSANOW))

    def press(keys):
        os.write(master, keys)

    yield press

    os.close(master)


@pytest.mark.parametrize('keys, key', [
    (b'\n', '\n'),
    (b'q', 'q'),
    (b'\x03', const.KEY_CTRL_C),
    (b'\x1b', const.KEY_ESCAPE),
    (b'\x1b[A', const.KEY_UP),
    (b'\x1b[B', const.KEY_DOWN)])
def test_get_key(pressed, keys, key):
    pressed(keys)
    assert unix.get_key() == key


def test_get_key_without_tty(monkeypatch, tmpdir):
    with tmpdir.join('stdin').ensure().open() as stdin:
        monkeypatch.setattr('sys.stdin', stdin)
        assert unix.get_key() == '\n'
