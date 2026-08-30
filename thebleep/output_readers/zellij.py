# -*- encoding: utf-8 -*-

"""Read the current Zellij pane without running the failed command again."""

import os

from ..utils import which
from . import pane


def is_available():
    """Whether this process is inside a Zellij terminal pane."""
    return bool(os.environ.get('ZELLIJ_PANE_ID') and which('zellij'))


def _capture():
    executable = which('zellij')
    pane_id = os.environ.get('ZELLIJ_PANE_ID')
    if not executable or not pane_id:
        return None
    return pane.capture(
        [executable, 'action', 'dump-screen', '--pane-id', pane_id, '--full'],
        'zellij')


def get_output(script, expanded):
    """Return the current pane's output, or ``None`` on weak boundaries."""
    capture = _capture()
    return pane.output(script, capture) if capture is not None else None
