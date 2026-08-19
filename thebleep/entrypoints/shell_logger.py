import array
import fcntl
from functools import partial
import mmap
import os
import pty
import select
import signal
import sys
import termios
import time
import tty
from .. import logs, const


def _record(f, data):
    """Appends what scrolled past to the recording, oldest first out.

    The recording is a fixed window: when it is full the oldest ten kilobytes
    are dropped and everything after them shifts down. The chunk that did not
    fit is written after the shift, which it used to be not -- it was simply
    lost, so a session that filled the window dropped up to a kilobyte of
    output every time it wrapped, and a correction could be made from a hole.

    """
    try:
        f.write(data)
    except ValueError:
        position = const.LOG_SIZE_IN_BYTES - const.LOG_SIZE_TO_CLEAN
        f.move(0, const.LOG_SIZE_TO_CLEAN, position)
        f.seek(position)
        f.write(b'\x00' * const.LOG_SIZE_TO_CLEAN)
        f.seek(position)
        try:
            f.write(data)
        except ValueError:                                   # pragma: no cover
            pass


def _write_all(fd, data):
    """Writes every byte, or gives up when there is nowhere to write them."""
    while data:
        try:
            written = os.write(fd, data)
        except OSError:
            return False
        data = data[written:]
    return True


def _set_pty_size(master_fd):
    buf = array.array('h', [0, 0, 0, 0])
    fcntl.ioctl(pty.STDOUT_FILENO, termios.TIOCGWINSZ, buf, True)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, buf)


CHUNK = 1024


def _copy(master_fd, record):
    """Passes the terminal through to the shell, keeping a copy.

    Not `pty._copy`. Two reasons, and the first is a bug: when *our* terminal
    goes away -- the window is closed, the ssh connection drops -- reading our
    own stdin returns nothing more, and `pty._copy` responds by dropping stdin
    from the set it waits on and carrying on waiting for a shell that nobody
    can type at. The logger, the shell inside it and the recording all outlive
    the terminal, and an idle session leaves them there indefinitely. Here, our
    stdin ending means the session ended.

    The second is that it is a private function, and this has to keep working
    across every Python from 3.9 to 3.14.

    """
    fds = [master_fd, pty.STDIN_FILENO]
    while True:
        try:
            readable = select.select(fds, [], [])[0]
        except InterruptedError:                             # pragma: no cover
            continue
        except OSError:                                      # pragma: no cover
            return

        if master_fd in readable:
            try:
                data = os.read(master_fd, CHUNK)
            except OSError:
                data = b''
            if not data:
                return          # the shell we started has finished
            record(data)
            if not _write_all(pty.STDOUT_FILENO, data):
                return          # nowhere left to show it

        if pty.STDIN_FILENO in readable:
            try:
                data = os.read(pty.STDIN_FILENO, CHUNK)
            except OSError:
                data = b''
            if not data:
                return          # our terminal has gone
            if not _write_all(master_fd, data):
                return


def _reap(pid, master_fd):
    """Ends the shell we started, and reports how it went.

    Closing the master hangs its terminal up, which is what makes a shell
    waiting at a prompt leave. A shell that stays anyway is not left running
    without a terminal for the rest of the login session.

    """
    try:
        os.close(master_fd)
    except OSError:                                          # pragma: no cover
        pass

    for signal_number in (None, signal.SIGHUP, signal.SIGKILL):
        if signal_number is not None:                        # pragma: no cover
            try:
                os.kill(pid, signal_number)
            except OSError:
                pass
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                finished, status = os.waitpid(pid, os.WNOHANG)
            except OSError:                                  # pragma: no cover
                return 0
            if finished:
                return status
            time.sleep(0.02)
    return 0                                                 # pragma: no cover


def _spawn(shell, record):
    """Runs `shell` in a terminal of its own, copying both ways.

    A version of `pty.spawn` that also keeps the child's window the same size
    as ours, and that puts the terminal back the way it found it however it
    leaves -- which the version this replaced only did when the copy loop had
    raised, so a shell that exited normally left the terminal in raw mode.

    """
    pid, master_fd = pty.fork()

    if pid == pty.CHILD:                                     # pragma: no cover
        os.execlp(shell, shell)

    try:
        mode = tty.tcgetattr(pty.STDIN_FILENO)
        tty.setraw(pty.STDIN_FILENO)
        restore = True
    except tty.error:    # This is the same as termios.error
        restore = False

    try:
        _set_pty_size(master_fd)
        signal.signal(signal.SIGWINCH, lambda *_: _set_pty_size(master_fd))
    except (OSError, ValueError):                            # pragma: no cover
        pass

    try:
        _copy(master_fd, record)
    finally:
        if restore:
            try:
                tty.tcsetattr(pty.STDIN_FILENO, tty.TCSAFLUSH, mode)
            except tty.error:                                # pragma: no cover
                pass

    return _reap(pid, master_fd)


def _open_log(path):
    """Creates the recording, readable and writable by nobody else.

    What ends up in this file is everything that scrolls past in the terminal
    for as long as the shell lives: the contents of every file read, every
    token a command prints, every password typed at a prompt that echoes. It
    used to be created with no mode at all, which means 0666 less the umask --
    world-readable on a normal machine, in a directory everyone can read.

    `O_EXCL` and `O_NOFOLLOW` because the directory may be a shared one: with
    `O_CREAT` alone, a name somebody else got to first is opened rather than
    refused, and a symlink left there is followed to wherever it points.

    """
    flags = (os.O_CREAT | os.O_EXCL | os.O_RDWR
             | getattr(os, 'O_NOFOLLOW', 0)
             | getattr(os, 'O_CLOEXEC', 0))
    return os.open(path, flags, 0o600)


def _remove(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _leave_on(*signals):
    """Turns the signals that end a session into an ordinary exit.

    So that the `finally` below runs and the recording goes with the session
    that made it. Closing a terminal window sends `SIGHUP` to the process group
    with the terminal in front of it, which is this one; `SIGTERM` is what a
    session manager sends on the way out. Neither used to remove anything, and
    the megabyte of everything that had scrolled past stayed on disk.

    `SIGKILL` cannot be caught by anyone, which is what the shell-side `trap` in
    the instant-mode alias is a backstop for.

    """
    def leave(number, frame):
        sys.exit(128 + number)

    for number in signals:
        try:
            signal.signal(number, leave)
        except (ValueError, OSError, AttributeError):     # pragma: no cover
            pass


def shell_logger(output):
    """Logs shell output to the `output`.

    Works like unix script command with `-f` flag.

    """
    if not os.environ.get('SHELL'):
        logs.warn("Shell logger doesn't support your platform.")
        sys.exit(1)

    try:
        fd = _open_log(output)
    except OSError as error:
        logs.warn(u"Can't record this shell's output to {}: {}".format(
            output, error))
        sys.exit(1)

    _leave_on(signal.SIGHUP, signal.SIGTERM)
    try:
        os.write(fd, b'\x00' * const.LOG_SIZE_IN_BYTES)
        buffer = mmap.mmap(fd, const.LOG_SIZE_IN_BYTES,
                           mmap.MAP_SHARED, mmap.PROT_WRITE)
        return_code = _spawn(os.environ['SHELL'],
                             partial(_record, buffer))
    finally:
        # The recording belongs to the session that made it, and the session is
        # over. Removed here rather than only by the shell that started us,
        # because that shell is blocked waiting for this process and does not
        # get to its own trap until this one has gone.
        _remove(output)

    sys.exit(return_code)
