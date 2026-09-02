"""`python -m thebleep` corrects a command, the same way the command does.

It exists so that Windows can skip the launcher stub pip installs alongside a
console script -- that stub starts a second process, and starting a process is
the most expensive thing Windows does. A way in that nothing exercises is a way
in that will quietly stop working, so this runs it.

"""

import os
import subprocess

import pytest
import sys

import thebleep.__main__
from thebleep.entrypoints.main import main

# Captured at import, before the fixtures replace `os.environ` with a bare one.
# Windows will not start an interpreter without `ComSpec` and `SystemRoot`, and
# a cut-down environment got `shell not found` out of the re-run and
# `_Py_HashRandomization_Init` out of the interpreter itself.
REAL_ENVIRONMENT = dict(os.environ)


@pytest.fixture(autouse=True, scope='module')
def _a_home_of_the_tests_own(tmp_path_factory):
    """The real environment, but not the real config and cache: the program
    run here records what it does, and it was recording into whoever's
    `~/.config/thebleep` ran the suite."""
    home = tmp_path_factory.mktemp('home')
    saved = {key: REAL_ENVIRONMENT.get(key)
             for key in ('XDG_CONFIG_HOME', 'XDG_CACHE_HOME')}
    REAL_ENVIRONMENT['XDG_CONFIG_HOME'] = str(home / 'config')
    REAL_ENVIRONMENT['XDG_CACHE_HOME'] = str(home / 'cache')
    yield
    for key, value in saved.items():
        if value is None:
            REAL_ENVIRONMENT.pop(key, None)
        else:
            REAL_ENVIRONMENT[key] = value


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


def test_a_path_to_it_runs_too(tmpdir):
    """`python path/to/thebleep/__main__.py`, which is how a clone is run.

    The alias of a checkout names this file by path, so it has to work as a
    plain script and not only as `-m thebleep`.

    """
    main_py = os.path.join(os.path.dirname(os.path.abspath(
        thebleep.__main__.__file__)), '__main__.py')
    environment = dict(REAL_ENVIRONMENT, TB_SHELL='bash')
    environment.pop('PYTHONPATH', None)
    result = subprocess.run(
        [sys.executable, main_py, '--version'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
        cwd=str(tmpdir))

    printed = (result.stdout + result.stderr).decode('utf-8', 'replace')
    assert result.returncode == 0, printed
    assert 'The Bleep' in printed


def test_running_it_by_path_does_not_shadow_the_standard_library():
    """The bug this is named after, which cost an afternoon.

    Running a file puts *that file's own directory* on `sys.path`, and for this
    file that is the package directory -- so `thebleep/types.py` answered for
    the standard library's `types`, and the next thing to want `enum` died on an
    import that had nothing to do with it. Whether it bit at all depended on
    which modules the interpreter had already loaded, so it worked on the
    machine it was written on and failed in a container.

    `-S` is what makes this deterministic: without `site` the interpreter has
    imported far less by the time `__main__.py` runs, which is the state the
    shadowing needs to show itself. `-S` also hides `site-packages`, so the
    dependencies are put back by hand.

    """
    main_py = os.path.join(os.path.dirname(os.path.abspath(
        thebleep.__main__.__file__)), '__main__.py')
    environment = dict(REAL_ENVIRONMENT, TB_SHELL='bash',
                       PYTHONPATH=os.pathsep.join(sys.path))
    result = subprocess.run(
        [sys.executable, '-S', main_py, '--version'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)

    errors = result.stderr.decode('utf-8', 'replace')
    assert 'attempted relative import' not in errors, errors
    assert result.returncode == 0, errors
