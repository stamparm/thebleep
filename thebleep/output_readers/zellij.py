# -*- encoding: utf-8 -*-

"""Read the current Zellij pane without running the failed command again."""

import os

from ..utils import which


def is_available():
    """Whether this process is inside a Zellij terminal pane."""
    return bool(os.environ.get('ZELLIJ_PANE_ID') and which('zellij'))


def _capture():
    from . import pane

    executable = which('zellij')
    pane_id = os.environ.get('ZELLIJ_PANE_ID')
    if not executable or not pane_id:
        return None
    # `zellij action dump-screen <PATH> [--full]` writes the focused pane to
    # a file; there is no flag naming a pane and nothing on stdout. The old
    # `--pane-id` form was rejected by zellij and this backend never answered.
    import tempfile

    handle, path = tempfile.mkstemp(prefix='thebleep-zellij-')
    os.close(handle)
    try:
        if pane.capture([executable, 'action', 'dump-screen', path, '--full'],
                        'zellij') is None:
            return None
        with open(path, 'rb') as dumped:
            raw = dumped.read(pane.MAX_CAPTURE + 1)
    except OSError:
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if len(raw) > pane.MAX_CAPTURE:
        return None
    return raw.decode('utf-8', errors='replace')


def get_output(script, expanded):
    """Return the current pane's output, or ``None`` on weak boundaries."""
    from . import pane

    capture = _capture()
    return pane.output(script, capture) if capture is not None else None
