# -*- coding: utf-8 -*-

"""What the Nushell alias does in a real Nushell.

Nushell has no `eval`, so a correction is written into the line editor with
`commandline edit --replace` and the user submits it. That is the only claim
worth checking, and the only way to check it is to run Nushell in front of a
terminal and look at what the next prompt says.

Driven by hand rather than through pexpect, because Nushell asks the terminal
where the cursor is (`ESC [ 6 n`) before drawing a prompt and waits for the
answer. A bare pty has nobody to give one, so the reader below does.

Skipped when `nu` is not installed; `tests/Dockerfile` has one.

"""

import os
import re
import shutil
import struct
import sys
import time
import pytest
from thebleep.shells import Nushell

if sys.platform == 'win32':  # pragma: no cover
    pytest.skip('needs a pty', allow_module_level=True)

import fcntl  # noqa: E402
import pty  # noqa: E402
import select  # noqa: E402
import termios  # noqa: E402

DEVICE_STATUS_REPORT = re.compile(rb'\x1b\[6n')
CURSOR_IS_AT_THE_TOP = b'\x1b[1;1R'

# Nushell is a big program that reads a config file and builds a completion
# engine before its first prompt, and everything here waits on that.
STARTUP = 6.0
STEP = 1.5
SETTLE = 4.0


def _strip(text):
    """The characters, without the escape sequences that placed them."""
    text = re.sub(r'\x1b\][^\x07\x1b]*(\x07|\x1b\\)', '', text)
    text = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', text)
    return re.sub(r'\x1b[=>78]', '', text)


class Terminal(object):
    """Just enough of one for Nushell to draw a prompt in."""

    def __init__(self, argv, environment):
        self.output = b''
        self.pid, self.fd = pty.fork()
        if self.pid == 0:                                   # pragma: no cover
            # `execvpe`, and not assigning to `os.environ` first: the suite
            # replaces `os.environ` with a plain dict, which puts nothing in
            # the environment the child would actually be handed.
            os.execvpe(argv[0], argv, environment)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                    struct.pack('HHHH', 40, 160, 0, 0))

    def read_for(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            if not select.select([self.fd], [], [], 0.1)[0]:
                continue
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                return
            if not data:
                return
            self.output += data
            if DEVICE_STATUS_REPORT.search(data):
                os.write(self.fd, CURSOR_IS_AT_THE_TOP)

    def type(self, text):
        os.write(self.fd, text.encode('utf-8'))
        self.read_for(STEP)

    @property
    def screen(self):
        return _strip(self.output.decode('utf-8', 'replace'))

    def close(self):
        try:
            os.kill(self.pid, 9)
            os.waitpid(self.pid, 0)
        except OSError:                                     # pragma: no cover
            pass


@pytest.fixture
def nushell(tmpdir):
    if shutil.which('nu') is None:
        pytest.skip('nu is not installed')

    # A stand-in for `thebleep`: it reports what it was given on stderr, the way
    # the real one writes its suggestion there, and answers with a correction.
    fake = tmpdir.join('thebleep')
    fake.write(u'#!/bin/sh\n'
               u'echo "SAW $TB_SHELL $TB_ALIAS -- $*" 1>&2\n'
               u'echo "echo RANMARK"\n')
    os.chmod(str(fake), 0o755)

    config = tmpdir.mkdir('nushell-config')
    config.join('config.nu').write_text(
        Nushell().app_alias('bleep'), 'utf-8')

    terminal = Terminal(
        ['nu', '--config', str(config.join('config.nu')), '-i'],
        {'PATH': '{}{}{}'.format(str(tmpdir), os.pathsep, os.environ['PATH']),
         'HOME': str(tmpdir), 'TERM': 'xterm-256color',
         'XDG_CONFIG_HOME': str(config.dirname),
         'LC_ALL': 'C.UTF-8', 'LANG': 'C.UTF-8'})
    terminal.read_for(STARTUP)
    terminal.output = b''
    yield terminal
    terminal.close()


class TestNushellForReal(object):
    def test_the_correction_lands_in_the_command_line(self, nushell):
        nushell.type(u'gti status\r')
        nushell.type(u'bleep\r')
        nushell.read_for(SETTLE)
        screen = nushell.screen
        # It was handed the command that failed, and told which shell it is in.
        assert 'SAW nu bleep -- gti status' in screen
        # And the correction is on the line rather than in the scrollback of a
        # command that ran: every RANMARK on the screen is one the line editor
        # is showing, none is one that `echo` printed.
        assert 'echo RANMARK' in screen
        assert screen.count('RANMARK') == screen.count('echo RANMARK')

    def test_the_command_line_is_editable_and_runs_what_you_submit(
            self, nushell):
        nushell.type(u'gti status\r')
        nushell.type(u'bleep\r')
        nushell.read_for(SETTLE)
        nushell.type(u'-EDITED\r')
        nushell.read_for(SETTLE)
        assert 'RANMARK-EDITED' in nushell.screen
