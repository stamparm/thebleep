# -*- encoding: utf-8 -*-

"""Read the current tmux pane without running the failed command again."""

import os

from ..utils import which


def is_available():
    """Whether this process is inside a tmux pane we can inspect."""
    return bool(os.environ.get('TMUX') and os.environ.get('TMUX_PANE')
                and which('tmux'))


def _capture():
    from . import pane

    executable = which('tmux')
    tmux_state = os.environ.get('TMUX', '')
    if not tmux_state:
        return None
    socket = tmux_state.split(',', 1)[0]
    pane_id = os.environ.get('TMUX_PANE')
    if not executable or not socket or not pane_id:
        return None

    return pane.capture(
        [executable, '-S', socket, 'capture-pane', '-p', '-J', '-t', pane_id],
        'tmux')


def _output(script, capture):
    from . import pane

    return pane.output(script, capture)


def get_output(script, expanded):
    """Return the current pane's output, or ``None`` when boundaries are weak."""
    capture = _capture()
    return _output(script, capture) if capture is not None else None
