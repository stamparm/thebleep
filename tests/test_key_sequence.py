# -*- encoding: utf-8 -*-

"""Reading one keypress, and only one.

A key used to be read as "up to six bytes, whatever is there", which meant a
key arriving with something behind it swallowed the lot. `y` followed by Enter
-- which is how everybody answers a `[y/N]` prompt -- arrived as `y\\r`, and
`y\\r` is not `y`, so the answer was read as **no**. That is a prompt guarding
whether the previous command runs a second time, so getting it backwards
silently reversed the user's consent.

Reproduced through a real terminal before it was fixed, and again after:

    just y                     -> YES
    y then Enter, together     -> NO      <- before
    y then Enter, together     -> YES     <- after

"""

import sys
import builtins
import pytest

pytestmark = pytest.mark.skipif(sys.platform == 'win32',
                                reason='Windows reads keys its own way')


@pytest.fixture
def unix():
    from thebleep.system import unix

    return unix


class TestWhatCountsAsFinished(object):
    @pytest.mark.parametrize('sequence, unfinished', [
        # An escape sequence arrives in pieces: ESC, then `[`, then the letter.
        (b'\x1b', True),
        (b'\x1b[', True),
        (b'\x1b[A', False),
        (b'\x1b[B', False),
        # An ordinary key is one byte and is done.
        (b'y', False),
        (b'n', False),
        (b'\r', False),
        (b'\x03', False),
        # A character outside ASCII is two to four bytes of UTF-8, and half of
        # one is not a keypress.
        (b'\xc3', True),
        (b'\xc3\xa9', False),
        (b'\xe2', True),
        (b'\xe2\x82', True),
        (b'\xe2\x82\xac', False),
        (b'\xf0\x9f', True),
        (b'\xf0\x9f\x98\x80', False),
    ])
    def test_it_knows(self, unix, sequence, unfinished):
        assert unix._is_incomplete(sequence) is unfinished

    @pytest.mark.parametrize('first, length', [
        (0x41, 1),          # 'A'
        (0xc3, 2),          # é
        (0xe2, 3),          # €
        (0xf0, 4),          # an emoji
        (0x80, 1),          # a stray continuation byte: not a start, so one
    ])
    def test_how_long_a_character_is(self, unix, first, length):
        assert unix._utf8_length(first) == length


class TestReadingOneKey(object):
    """`os.read` is asked for one byte, not six.

    The number is the whole bug, so it is the thing asserted.

    """

    @pytest.fixture
    def terminal(self, mocker, unix):
        """A terminal with `keys` waiting to be read, one byte per call."""
        mocker.patch.object(unix.sys, 'stdin')
        mocker.patch('termios.tcgetattr', return_value=[])
        mocker.patch('termios.tcsetattr')
        mocker.patch('tty.setraw')

        def _waiting(keys):
            pending = list(keys)

            def read(fd, size):
                assert size == 1, \
                    'asked for {} bytes; reading more than one swallows ' \
                    'whatever came next'.format(size)
                return bytes([pending.pop(0)]) if pending else b''

            mocker.patch.object(unix.os, 'read', side_effect=read)
            mocker.patch('select.select',
                         side_effect=lambda *a: ([1], [], []) if pending
                         else ([], [], []))
            return pending

        return _waiting

    def test_y_with_an_enter_behind_it_is_still_y(self, unix, terminal):
        pending = terminal(b'y\r')
        assert unix.read_key_sequence() == 'y'
        assert pending == [13], 'the Enter is left for the next prompt'

    def test_a_newline_behind_it_too(self, unix, terminal):
        terminal(b'y\n')
        assert unix.read_key_sequence() == 'y'

    def test_an_arrow_key_is_read_whole(self, unix, terminal):
        terminal(b'\x1b[B')
        assert unix.read_key_sequence() == '\x1b[B'

    def test_an_arrow_key_with_an_enter_behind_it(self, unix, terminal):
        """Fast typing, key repeat and paste all do this, and it used to be
        dropped with no redraw and no beep."""
        pending = terminal(b'\x1b[B\r')
        assert unix.read_key_sequence() == '\x1b[B'
        assert pending == [13]

    def test_escape_on_its_own(self, unix, terminal):
        terminal(b'\x1b')
        assert unix.read_key_sequence() == '\x1b'

    def test_no_terminal_means_no_consent(self, unix, mocker):
        """A pipe, a subprocess or CI: nobody can answer, so it is a refusal
        rather than a guess."""
        mocker.patch.object(unix.sys, 'stdin')
        import termios

        mocker.patch('termios.tcgetattr', side_effect=termios.error)
        assert unix.read_key_sequence() == '\x03'


class TestCtrlCBeforeRawMode(object):
    """Ctrl+C is `\\x03` once the terminal is raw, and a `KeyboardInterrupt`
    before that.

    The window is not theoretical. The three modules that make a terminal raw
    are imported lazily, so the *first* keypress in a process waits through
    finding, compiling and writing their bytecode -- and a real CI run caught
    the interrupt arriving inside `import tty`, which came out of the prompt as
    a traceback rather than as an abandoned suggestion. The Windows reader had
    the same fault by a different route.

    """

    def test_an_interrupt_during_the_imports(self, unix, mocker):
        """Which is where CI caught it."""
        real_import = builtins.__import__

        def interrupt(name, *args, **kwargs):
            if name == 'tty':
                raise KeyboardInterrupt
            return real_import(name, *args, **kwargs)

        mocker.patch.object(builtins, '__import__', side_effect=interrupt)
        assert unix.read_key_sequence() == '\x03'

    def test_an_interrupt_between_asking_and_raw_mode(self, unix,
                                                      mocker):
        """`tcgetattr` has answered, `setraw` has not run, and the default
        SIGINT handler is still the one installed."""
        mocker.patch('sys.stdin.fileno', return_value=0)
        mocker.patch('termios.tcgetattr', return_value=[])
        restore = mocker.patch('termios.tcsetattr')
        mocker.patch('tty.setraw', side_effect=KeyboardInterrupt)

        assert unix.read_key_sequence() == '\x03'
        # And the terminal is put back the way it was found.
        assert restore.called

    def test_and_it_reads_as_an_abort(self, unix, mocker):
        """Which is the whole point: the same answer as the byte itself."""
        from thebleep import const

        mocker.patch.object(unix, 'read_key_sequence', return_value='\x03')
        assert unix.get_key() is const.KEY_CTRL_C
