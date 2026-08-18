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

# Captured at import, before the fixtures replace `os.environ` with a bare one.
# Windows will not start an interpreter without `ComSpec` and `SystemRoot`, and
# a cut-down environment got `shell not found` out of the re-run and
# `_Py_HashRandomization_Init` out of the interpreter itself.
REAL_ENVIRONMENT = dict(os.environ)


def test_it_is_the_same_entry_point():
    assert thebleep.__main__.main is main


def test_it_corrects_a_command():
    """One subprocess, because a module run as `-m` is only itself in one.

    """
    environment = dict(REAL_ENVIRONMENT, TB_SHELL='bash',
                       PYTHONPATH=os.pathsep.join(sys.path))
    result = subprocess.run(
        [sys.executable, '-m', 'thebleep', '--yes', '--', 'ehco', 'hello'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)

    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    # It corrected the typo -- not necessarily to `echo hello`. `echo` is a
    # shell builtin on Windows rather than a file on `PATH`, so the nearest
    # thing to `ehco` there is whatever is actually installed. What this is
    # testing is that the entry point runs and produces a suggestion.
    suggestion = result.stdout.decode('utf-8', 'replace').strip()
    assert suggestion, 'no suggestion came back'
    assert suggestion.endswith('hello')
    assert 'ehco' not in suggestion
