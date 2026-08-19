# -*- encoding: utf-8 -*-

"""Reading a correction out of a recorded session.

The recording is a fixed one-megabyte window written by `shell_logger`, and once
a session has printed a megabyte it wraps: the oldest ten kilobytes are dropped
and everything after them shifts down. Which means the first byte of what gets
read is whatever byte happened to land there -- and if the output has multibyte
characters in it, that is a continuation byte roughly `1 - 1/n` of the time.

`bytes.decode()` raises on that, `get_output` caught only `OSError` and
`ScriptNotInLog`, and what the user saw was a traceback out of the middle of a
correction. So the boundary is the case these are mostly about.

"""

import os
import pytest
from thebleep import const
from thebleep.output_readers import read_log

MARK = const.USER_COMMAND_MARK


def _log(tmpdir, *commands):
    """A recording of `(script, output)` pairs, the size a real one is.

    Written the way the shell writes it: the prompt carries the mark, the script
    is echoed after it, and the output follows on its own lines.

    """
    text = u''
    for script, output in commands:
        text += u'{}$ {}\r\n'.format(MARK, script)
        if output:
            text += output + u'\r\n'
    text += u'{}$ '.format(MARK)
    return _write(tmpdir, text.encode('utf-8'))


def _write(tmpdir, raw):
    """Puts `raw` at the front of a full-size recording and points env at it."""
    path = tmpdir.join('log')
    padded = raw[:const.LOG_SIZE_IN_BYTES]
    padded += b'\x00' * (const.LOG_SIZE_IN_BYTES - len(padded))
    with open(str(path), 'wb') as handle:
        handle.write(padded)
    os.environ['THEBLEEP_OUTPUT_LOG'] = str(path)
    os.environ['PS1'] = MARK + u'$ '
    return str(path)


@pytest.fixture(autouse=True)
def a_terminal(monkeypatch):
    """A width, so that pyte wraps where these tests expect it to."""
    monkeypatch.setattr(read_log, 'get_terminal_size',
                        lambda: os.terminal_size((80, 24)))


class TestWhatItReads(object):
    def test_the_output_of_the_command_it_is_asked_about(self, tmpdir,
                                                         os_environ):
        _log(tmpdir, (u'ehco test', u'ehco: command not found'),
             (u'ls', u'a  b  c'))
        assert read_log.get_output(u'ehco test') == u'ehco: command not found'

    def test_the_latest_of_two_runs_of_the_same_command(self, tmpdir,
                                                        os_environ):
        _log(tmpdir, (u'flaky', u'first'), (u'flaky', u'second'))
        assert read_log.get_output(u'flaky') == u'second'

    def test_a_command_that_printed_nothing(self, tmpdir, os_environ):
        """An empty answer is an answer, and must not be read as a failure."""
        _log(tmpdir, (u'true', u''))
        assert read_log.get_output(u'true') == u''


class TestUnicode(object):
    def test_multibyte_output(self, tmpdir, os_environ):
        _log(tmpdir, (u'say', u'caf\xe9 — © 你好'))
        assert read_log.get_output(u'say') == u'caf\xe9 — © 你好'

    @pytest.mark.parametrize('shift', (1, 2, 4, 5))
    def test_a_window_that_starts_in_the_middle_of_a_character(
            self, tmpdir, os_environ, shift):
        """What wrapping does: the first character has lost its first byte.

        Every offset into a three-byte character is tried, because the ring
        drops ten kilobytes at a time and has no idea what is at the seam.

        """
        raw = (u'你好 caf\xe9\r\n{}$ say\r\nthe answer\r\n{}$ '
               .format(MARK, MARK).encode('utf-8'))
        assert 0x80 <= raw[shift] <= 0xbf, 'not a continuation byte'
        _write(tmpdir, raw[shift:])
        assert read_log.get_output(u'say') == u'the answer'

    def test_output_that_was_never_utf8(self, tmpdir, os_environ):
        """A command that printed a JPEG is not a reason to raise."""
        raw = (u'{}$ dump\r\n'.format(MARK).encode('utf-8')
               + b'\xff\xd8\xff\xe0 not text \x80\x81'
               + u'\r\n{}$ '.format(MARK).encode('utf-8'))
        _write(tmpdir, raw)
        assert 'not text' in read_log.get_output(u'dump')

    def test_a_character_cut_off_at_the_far_end(self, tmpdir, os_environ):
        """The window ends where it ends too, and that is not fatal either."""
        raw = (u'{}$ say\r\nthe answer caf'.format(MARK).encode('utf-8')
               + u'\xe9'.encode('utf-8')[:1])
        _write(tmpdir, raw)
        assert 'the answer' in read_log.get_output(u'say')


class TestLargeOutput(object):
    def _lines(self, count, text):
        return u'\r\n'.join(u'{} {}'.format(number, text)
                            for number in range(count))

    def test_a_megabyte_of_ascii(self, tmpdir, os_environ):
        _log(tmpdir, (u'flood', self._lines(20000, u'x' * 40)),
             (u'ehco test', u'ehco: command not found'))
        assert read_log.get_output(u'ehco test') == u'ehco: command not found'

    def test_a_megabyte_of_unicode_that_wrapped(self, tmpdir, os_environ):
        """The two together, which is the combination that used to crash.

        Big enough to be truncated to the window, multibyte enough that the
        truncation lands inside a character, and the command being asked about
        is the last one, which is where a real correction reads from.

        """
        text = (u'{}$ flood\r\n'.format(MARK)
                + self._lines(60000, u'caf\xe9 你好')
                + u'\r\n{}$ ehco test\r\nehco: command not found\r\n{}$ '
                .format(MARK, MARK))
        raw = text.encode('utf-8')
        assert len(raw) > const.LOG_SIZE_IN_BYTES, 'not big enough to wrap'
        # What the ring leaves behind: the tail, starting wherever it starts.
        _write(tmpdir, raw[-const.LOG_SIZE_IN_BYTES:])
        assert read_log.get_output(u'ehco test') == u'ehco: command not found'


class TestWhenItCannotAnswer(object):
    """Each of these returns `None`, which is what makes the fallback work."""

    def test_no_recording_configured(self, os_environ):
        assert read_log.get_output(u'ls') is None

    def test_no_mark_in_the_prompt(self, tmpdir, os_environ):
        _log(tmpdir, (u'ls', u'a'))
        os.environ['PS1'] = u'$ '
        assert read_log.get_output(u'ls') is None

    def test_a_recording_that_is_not_there(self, tmpdir, os_environ):
        _log(tmpdir, (u'ls', u'a'))
        os.environ['THEBLEEP_OUTPUT_LOG'] = str(tmpdir.join('gone'))
        assert read_log.get_output(u'ls') is None

    def test_a_command_that_is_not_in_it(self, tmpdir, os_environ):
        _log(tmpdir, (u'ls', u'a'))
        assert read_log.get_output(u'ehco test') is None
