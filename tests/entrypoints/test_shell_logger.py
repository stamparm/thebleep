# -*- coding: utf-8 -*-

"""The recording instant mode makes, and what it must not leave behind.

What goes into this file is everything that scrolls past in a terminal for as
long as the shell lives: the contents of every file read, every token a command
prints, every password typed at a prompt that echoes. So two of these are about
who can read it and whether it survives the session, rather than about whether
the feature works.

"""

import os
import stat
import sys
import pytest

if sys.platform == 'win32':  # pragma: no cover
    pytest.skip('the shell logger is POSIX only', allow_module_level=True)

from thebleep import const                                       # noqa: E402
from thebleep.entrypoints import shell_logger as logger          # noqa: E402
from thebleep.shells import Bash, Zsh                            # noqa: E402
from thebleep.shells.generic import instant_log_path             # noqa: E402


@pytest.fixture
def temporary(tmpdir, monkeypatch):
    """`gettempdir` remembers its answer, so `TMPDIR` alone would not do."""
    import tempfile

    place = tmpdir.mkdir('temporary')
    monkeypatch.setattr(tempfile, 'tempdir', str(place))
    return str(place)


class TestWhereTheRecordingGoes(object):
    def test_the_runtime_directory_is_preferred(self, os_environ, tmpdir):
        """It belongs to one user and is mode 0700; /tmp is shared."""
        runtime = tmpdir.mkdir('runtime')
        os_environ['XDG_RUNTIME_DIR'] = str(runtime)
        assert instant_log_path().startswith(str(runtime))

    def test_the_temporary_directory_when_there_is_no_runtime_one(
            self, os_environ, temporary):
        assert instant_log_path().startswith(temporary)

    def test_a_runtime_directory_that_is_not_there_is_not_used(
            self, os_environ, tmpdir, temporary):
        os_environ['XDG_RUNTIME_DIR'] = str(tmpdir.join('gone'))
        assert instant_log_path().startswith(temporary)

    def test_two_shells_get_two_recordings(self, os_environ, temporary):
        assert instant_log_path() != instant_log_path()


class TestWhoCanReadIt(object):
    def test_it_is_readable_by_nobody_else(self, tmpdir):
        path = str(tmpdir.join('recording'))
        os.close(logger._open_log(path))
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, oct(mode)

    def test_a_file_that_is_already_there_is_refused(self, tmpdir):
        """The directory may be shared, so the name may not be ours."""
        path = tmpdir.join('recording')
        path.write('')
        with pytest.raises(OSError):
            logger._open_log(str(path))

    @pytest.mark.skipif(not hasattr(os, 'symlink'),
                        reason='needs symlinks')
    def test_a_symlink_left_in_the_way_is_not_followed(self, tmpdir):
        target = tmpdir.join('somebody-elses-file')
        target.write('important')
        link = str(tmpdir.join('recording'))
        os.symlink(str(target), link)
        with pytest.raises(OSError):
            logger._open_log(link)
        assert target.read() == 'important'


class TestTheRecordingItself(object):
    @pytest.fixture
    def window(self, monkeypatch):
        """A small recording, so that wrapping it does not take a megabyte."""
        monkeypatch.setattr(const, 'LOG_SIZE_IN_BYTES', 512)
        monkeypatch.setattr(const, 'LOG_SIZE_TO_CLEAN', 128)
        import mmap

        return mmap.mmap(-1, 512)

    def test_output_is_recorded(self, window):
        logger._record(window, b'hello')
        assert window[:5] == b'hello'

    def test_the_chunk_that_wraps_it_is_not_lost(self, window):
        """It used to be dropped, so a wrap left a hole to correct from."""
        logger._record(window, b'x' * 512)
        logger._record(window, b'the newest output')
        assert b'the newest output' in window[:]

    def test_the_oldest_output_is_what_goes(self, window):
        logger._record(window, b'FIRST' + b'x' * 507)
        logger._record(window, b'LAST')
        assert b'LAST' in window[:]
        assert b'FIRST' not in window[:]


class TestLeavingTheSession(object):
    def test_our_terminal_ending_ends_the_session(self, monkeypatch):
        """`pty._copy` waits on for a shell nobody can type at any more."""
        theirs, ours = os.pipe()          # nothing will ever be written
        empty_read, empty_write = os.pipe()
        os.close(empty_write)             # our stdin, already at end of file
        monkeypatch.setattr(logger.pty, 'STDIN_FILENO', empty_read)
        try:
            logger._copy(theirs, lambda data: None)
        finally:
            for fd in (theirs, ours, empty_read):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_the_shell_ending_ends_the_session(self, monkeypatch):
        theirs, ours = os.pipe()
        os.close(ours)                    # the shell has gone
        never, never_write = os.pipe()
        monkeypatch.setattr(logger.pty, 'STDIN_FILENO', never)
        try:
            logger._copy(theirs, lambda data: None)
        finally:
            for fd in (theirs, never, never_write):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_the_recording_goes_with_the_session(self, tmpdir, os_environ,
                                                 monkeypatch):
        path = str(tmpdir.join('recording'))
        os_environ['SHELL'] = '/bin/sh'
        monkeypatch.setattr(logger, '_spawn', lambda shell, record: 0)
        with pytest.raises(SystemExit):
            logger.shell_logger(path)
        assert not os.path.exists(path)

    def test_the_recording_goes_even_when_the_shell_blows_up(
            self, tmpdir, os_environ, monkeypatch):
        path = str(tmpdir.join('recording'))
        os_environ['SHELL'] = '/bin/sh'

        def explode(shell, record):
            raise RuntimeError('the pty went away')

        monkeypatch.setattr(logger, '_spawn', explode)
        with pytest.raises(RuntimeError):
            logger.shell_logger(path)
        assert not os.path.exists(path)


class TestTheAliasCleansUpToo(object):
    """A backstop for the one signal nothing can catch."""

    @pytest.mark.parametrize('shell_class', [Bash, Zsh])
    def test_a_trap_removes_the_recording(self, shell_class, os_environ):
        alias = shell_class().instant_mode_alias('bleep')
        assert "trap 'rm -f" in alias
        assert 'EXIT HUP INT TERM' in alias

    @pytest.mark.parametrize('shell_class', [Bash, Zsh])
    def test_the_path_is_quoted(self, shell_class, os_environ, tmpdir,
                                monkeypatch):
        """`TMPDIR` is somebody's to set, and a path may hold a space."""
        import tempfile

        awkward = tmpdir.mkdir('a directory')
        monkeypatch.setattr(tempfile, 'tempdir', str(awkward))
        alias = shell_class().instant_mode_alias('bleep')
        assert "'{}".format(awkward) in alias
