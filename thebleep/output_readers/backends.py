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

    __slots__ = ('name', 'replayless', '_available', '_read')

    def __init__(self, name, replayless, available, read):
        self.name = name
        self.replayless = replayless
        self._available = available
        self._read = read

    def is_available(self):
        return bool(self._available())

    def read(self, script, expanded):
        return self._read(script, expanded)


_registered = []


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


def _shell_logger_read(script, expanded):
    from . import shell_logger
    return shell_logger.get_output(script)


def _instant_available():
    from ..conf import settings
    return bool(settings.instant_mode)


def _instant_read(script, expanded):
    from . import read_log
    return read_log.get_output(script)


def _tmux_available():
    from . import tmux
    return tmux.is_available()


def _tmux_read(script, expanded):
    from . import tmux
    return tmux.get_output(script, expanded)


def _zellij_available():
    from . import zellij
    return zellij.is_available()


def _zellij_read(script, expanded):
    from . import zellij
    return zellij.get_output(script, expanded)


def _wezterm_available():
    from . import wezterm
    return wezterm.is_available()


def _wezterm_read(script, expanded):
    from . import wezterm
    return wezterm.get_output(script, expanded)


def _kitty_available():
    from . import kitty
    return kitty.is_available()


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
    shell_logger_available = (shell_logger_available
                              or _shell_logger_available)
    return (
        CaptureBackend('shell-logger', True, shell_logger_available,
                       _shell_logger_read),
        CaptureBackend('instant-log', True, _instant_available, _instant_read),
        CaptureBackend('zellij', True, _zellij_available, _zellij_read),
        CaptureBackend('wezterm', True, _wezterm_available, _wezterm_read),
        CaptureBackend('kitty', True, _kitty_available, _kitty_read),
        CaptureBackend('tmux', True, _tmux_available, _tmux_read),
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
    from ..conf import settings
    from ..shells import shell

    logger_configured = bool(os.environ.get(const.SHELL_LOGGER_SOCKET_ENV))
    try:
        logger_available = _shell_logger_available()
    except Exception:                                      # pragma: no cover
        logger_available = False

    try:
        shell_supports_log = bool(shell.supports_instant_mode())
    except Exception:                                      # pragma: no cover
        shell_supports_log = False

    capture = (
        CaptureBackend('shell-logger', True, _shell_logger_available,
                       _shell_logger_read),
        CaptureBackend('instant-log', True, _instant_available, _instant_read),
        CaptureBackend('zellij', True, _zellij_available, _zellij_read),
        CaptureBackend('wezterm', True, _wezterm_available, _wezterm_read),
        CaptureBackend('kitty', True, _kitty_available, _kitty_read),
        CaptureBackend('tmux', True, _tmux_available, _tmux_read),
        CaptureBackend('replay', False, lambda: True, _replay_read))
    result = []
    for backend in tuple(_registered) + capture:
        if backend.name == 'shell-logger':
            configured, available = logger_configured, logger_available
        elif backend.name == 'instant-log':
            configured = bool(settings.instant_mode)
            available = bool(configured and shell_supports_log)
        elif backend.name == 'tmux':
            configured = bool(os.environ.get('TMUX')
                              and os.environ.get('TMUX_PANE'))
            try:
                available = backend.is_available()
            except Exception:                                  # pragma: no cover
                available = False
        elif backend.name == 'zellij':
            configured = bool(os.environ.get('ZELLIJ_PANE_ID'))
            try:
                available = backend.is_available()
            except Exception:                                  # pragma: no cover
                available = False
        elif backend.name == 'wezterm':
            configured = bool(os.environ.get('WEZTERM_PANE'))
            try:
                available = backend.is_available()
            except Exception:                                  # pragma: no cover
                available = False
        elif backend.name == 'kitty':
            configured = bool(os.environ.get('KITTY_WINDOW_ID'))
            try:
                available = backend.is_available()
            except Exception:                                  # pragma: no cover
                available = False
        else:
            configured = True
            try:
                available = backend.is_available()
            except Exception:                                  # pragma: no cover
                available = False
        result.append({'name': backend.name,
                       'replayless': backend.replayless,
                       'configured': configured,
                       'available': available})
    return result


def clear_registered():
    """Clear extensions, for isolated embedders and tests."""
    del _registered[:]
