"""`python -m thebleep` corrects a command, the same way the command does.

It exists so that Windows can skip the launcher stub pip installs alongside a
console script -- that stub starts a second process, and starting a process is
the most expensive thing Windows does. A way in that nothing exercises is a way
in that will quietly stop working, so this runs it.

"""

import os
import subprocess
import sys

import thebleep.__main__
from thebleep.entrypoints.main import main


def test_it_is_the_same_entry_point():
    assert thebleep.__main__.main is main


def test_it_corrects_a_command():
    """One subprocess, because a module run as `-m` is only itself in one.

    The whole environment goes with it, not a hand-picked few variables.
    Windows needs more of it than looks reasonable to start an interpreter at
    all -- a cut-down one got `_Py_HashRandomization_Init: failed to get random
    numbers to initialize Python` before any of our code ran.

    """
    environment = dict(os.environ, TB_SHELL='bash',
                       PYTHONPATH=os.pathsep.join(sys.path))
    result = subprocess.run(
        [sys.executable, '-m', 'thebleep', '--yes', '--', 'ehco', 'hello'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)

    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    assert 'echo hello' in result.stdout.decode('utf-8', 'replace')
