# -*- encoding: utf-8 -*-

"""Capture backends shared by correction and diagnostics.

Each backend either returns the output it already has or returns ``None``. It
must never make a correction less safe by bypassing the replay gate. Keeping
the choice here gives terminal integrations one small seam to implement while
the existing readers remain lazy and independently testable.
"""

import os

from .. import const, logs


class CaptureBackend(object):
    """One ordered way to obtain output for a failed command."""

    __slots__ = ('name', 'replayless', '_available', '_read', '_configured',
                 '_status_available')

    def __init__(self, name, replayless, available, read, configured=None,
                 status_available=None):
        self.name = name
        self.replayless = replayless
        self._available = available
        self._read = read
        self._configured = configured or (lambda: True)
        self._status_available = status_available or available

    def is_available(self):
        return bool(self._available())

    def is_configured(self):
        return bool(self._configured())

    def is_status_available(self):
        return bool(self._status_available())

    def read(self, script, expanded):
        return self._read(script, expanded)


_registered = []


def _constant(value):
    """Return a predicate with a fixed answer for an embedding override."""
    def answer():
        return bool(value)
    return answer


def register(backend):
    """Add a backend before the built-ins, preserving fallback order."""
    if not isinstance(backend, CaptureBackend):
        raise TypeError('backend must be a CaptureBackend')
    if any(item.name == backend.name for item in _registered):
        raise ValueError('capture backend is already registered: {}'.format(
            backend.name))
    _registered.append(backend)


def _shell_logger_available():
    if not os.environ.get(const.SHELL_LOGGER_SOCKET_ENV):
        return False
    from . import shell_logger
    return shell_logger.is_available()


def _shell_logger_configured():
    return bool(os.environ.get(const.SHELL_LOGGER_SOCKET_ENV))


def _shell_logger_read(script, expanded):
    from . import shell_logger
    return shell_logger.get_output(script)


def _instant_available():
    from ..conf import settings
    return bool(settings.instant_mode)


def _instant_status_available():
    from ..shells import shell
    return bool(_instant_available() and shell.supports_instant_mode())


def _instant_configured():
    from ..conf import settings
    return bool(settings.instant_mode)


def _instant_read(script, expanded):
    from . import read_log
    return read_log.get_output(script)


def _tmux_available():
    from ..utils import which
    return bool(os.environ.get('TMUX') and os.environ.get('TMUX_PANE')
                and which('tmux'))


def _tmux_configured():
    return bool(os.environ.get('TMUX') and os.environ.get('TMUX_PANE'))


def _tmux_read(script, expanded):
    from . import tmux
    return tmux.get_output(script, expanded)


def _zellij_available():
    from ..utils import which
    return bool(os.environ.get('ZELLIJ_PANE_ID') and which('zellij'))


def _zellij_configured():
    return bool(os.environ.get('ZELLIJ_PANE_ID'))


def _zellij_read(script, expanded):
    from . import zellij
    return zellij.get_output(script, expanded)


def _wezterm_available():
    from ..utils import which
    return bool(os.environ.get('WEZTERM_PANE') and which('wezterm'))


def _wezterm_configured():
    return bool(os.environ.get('WEZTERM_PANE'))


def _wezterm_read(script, expanded):
    from . import wezterm
    return wezterm.get_output(script, expanded)


def _kitty_available():
    from ..utils import which
    window_id = os.environ.get('KITTY_WINDOW_ID', '')
    return bool(window_id.isdigit() and which('kitten'))


def _kitty_configured():
    return bool(os.environ.get('KITTY_WINDOW_ID'))


def _kitty_read(script, expanded):
    from . import kitty
    return kitty.get_output(script, expanded)


def _replay_available(script, expanded):
    from .. import replay
    return replay.is_allowed(script, expanded)


def _replay_read(script, expanded):
    from . import rerun
    return rerun.get_output(script, expanded)


def builtins(script, expanded, shell_logger_available=None):
    """Return built-ins in their safety and latency order."""
    if shell_logger_available is None:
        logger_available = _shell_logger_available
        logger_configured = _shell_logger_configured
    elif callable(shell_logger_available):
        logger_available = shell_logger_available
        logger_configured = _constant(True)
    else:
        # An explicit False is a test/embedding override, not a request to
        # inspect the host. The old ``value or detector`` form broke that
        # contract and could unexpectedly touch a socket path.
        logger_available = _constant(shell_logger_available)
        logger_configured = _constant(True)
    return (
        CaptureBackend('shell-logger', True, logger_available,
                       _shell_logger_read, logger_configured),
        CaptureBackend('instant-log', True, _instant_available, _instant_read,
                       _instant_configured, _instant_status_available),
        CaptureBackend('zellij', True, _zellij_available, _zellij_read,
                       _zellij_configured),
        CaptureBackend('wezterm', True, _wezterm_available, _wezterm_read,
                       _wezterm_configured),
        CaptureBackend('kitty', True, _kitty_available, _kitty_read,
                       _kitty_configured),
        CaptureBackend('tmux', True, _tmux_available, _tmux_read,
                       _tmux_configured),
        CaptureBackend('replay', False,
                       lambda: _replay_available(script, expanded),
                       _replay_read),
    )


def all_for(script, expanded, shell_logger_available=None):
    return tuple(_registered) + builtins(
        script, expanded, shell_logger_available)


def read(script, expanded, shell_logger_available=None):
    """Try registered and built-in backends, returning the first answer."""
    for backend in all_for(script, expanded, shell_logger_available):
        try:
            if not backend.is_configured():
                continue
            if not backend.is_available():
                continue
            output = backend.read(script, expanded)
        except Exception as error:                            # noqa: BLE001
            logs.debug(u'Capture backend {} failed: {}'.format(
                backend.name, error))
            continue
        if output is not None:
            return output
    return None


def status():
    """Describe configured capture mechanisms without running a command."""
    result = []
    # The same factory defines runtime ordering and doctor-visible status.
    # Replay is represented as an available fallback here without asking for
    # permission or inspecting a command, which status() must never do.
    capture = builtins('', '', shell_logger_available=None)
    capture = capture[:-1] + (CaptureBackend('replay', False, lambda: True,
                                             _replay_read),)
    for backend in tuple(_registered) + capture:
        try:
            configured = backend.is_configured()
            available = bool(configured and backend.is_status_available())
        except Exception:                                      # pragma: no cover
            configured, available = False, False
        result.append({'name': backend.name,
                       'replayless': backend.replayless,
                       'configured': configured,
                       'available': available})
    return result


def clear_registered():
    """Clear extensions, for isolated embedders and tests."""
    del _registered[:]
