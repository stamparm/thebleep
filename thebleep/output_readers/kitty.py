# -*- encoding: utf-8 -*-

"""Read the current kitty window without running the failed command again."""

import os

from ..utils import which


def _window_id():
    value = os.environ.get('KITTY_WINDOW_ID', '')
    return value if value.isdigit() else None


def is_available():
    """Whether kitty identifies this window and exposes its control client."""
    return bool(_window_id() and which('kitten'))


def _capture():
    from . import pane

    executable = which('kitten')
    window_id = _window_id()
    if not executable or not window_id:
        return None
    return pane.capture([
        executable, '@', 'get-text', '--match', 'id:{}'.format(window_id),
        '--extent', 'all'], 'kitty')


def get_output(script, expanded):
    """Return the current window's output, or ``None`` on weak boundaries."""
    from . import pane

    capture = _capture()
    return pane.output(script, capture) if capture is not None else None
