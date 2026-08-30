# -*- encoding: utf-8 -*-

"""Read the current WezTerm pane without running the failed command again."""

import os

from ..utils import which


def is_available():
    """Whether WezTerm identifies a pane and exposes its CLI."""
    return bool(os.environ.get('WEZTERM_PANE') and which('wezterm'))


def _capture():
    from . import pane

    executable = which('wezterm')
    pane_id = os.environ.get('WEZTERM_PANE')
    if not executable or not pane_id:
        return None
    return pane.capture([
        executable, 'cli', 'get-text', '--pane-id', pane_id,
        '--start-line=-1000000'], 'wezterm')


def get_output(script, expanded):
    """Return the current pane's output, or ``None`` on weak boundaries."""
    from . import pane

    capture = _capture()
    return pane.output(script, capture) if capture is not None else None
