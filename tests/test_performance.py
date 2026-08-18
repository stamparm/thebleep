# -*- coding: utf-8 -*-

"""Guards for the things that make The Bleep fast.

Wall-clock thresholds are worthless on a shared build machine, so these test
the structure instead: what gets imported before a correction starts, how many
rules a command is dispatched to, and the two pathological behaviours that used
to make a large output take seconds. Each one of these failing means a specific
optimisation has been undone.
"""

import os
import subprocess
import sys
import textwrap
import time
import pytest
from thebleep import rulepack
from thebleep.types import Command

# Captured before the fixtures replace `os.environ` with a bare one: starting a
# shell needs more of it than PATH, particularly on Windows.
REAL_ENVIRONMENT = dict(os.environ)

# Imported before a correction begins, this lot cost more than everything else
# the app does. Each is loaded only on the path that actually needs it.
SHOULD_NOT_BE_IMPORTED = [
    'pyte',        # rendering a captured screen, instant mode only
    'psutil',      # process trees, only when the shell is unknown or a re-run
                   # overruns
    'argparse',    # only for command lines the fast path declines
    'pprint',      # only to pretty-print settings into a debug line
    'dataclasses',  # dragged in by pprint
    'shelve',      # only for rules that keep a cache
    'dbm',         # dragged in by shelve
    'traceback',   # only when something has gone wrong
]

# Windows has to have its console set up before anything is written, and
# `win_unicode_console.readline_hook` imports `traceback` on the way in. From
# Python 3.14 `traceback` pulls `dataclasses` with it, by way of the `ast` and
# `inspect` machinery behind its nicer error messages. That is a dependency
# doing it rather than us, so the guard steps aside when it is the one
# responsible — `pprint`, our own reason for not wanting `dataclasses`, is
# still guarded on every platform.
IMPORTED_BY_THE_WINDOWS_CONSOLE = {'traceback', 'dataclasses'}


def _imported_modules(env=None):
    """Everything imported by loading the entry point, in a fresh process."""
    source = textwrap.dedent('''
        import sys
        import thebleep.entrypoints.main   # noqa: F401
        print('\\n'.join(sorted(sys.modules)))
    ''')
    environment = dict(REAL_ENVIRONMENT)
    environment.update(env or {})
    environment['TB_SHELL'] = 'bash'
    output = subprocess.check_output([sys.executable, '-c', source],
                                     env=environment)
    return set(output.decode('utf-8').split())


@pytest.fixture(scope='module')
def imported():
    return _imported_modules()


@pytest.mark.parametrize('module', SHOULD_NOT_BE_IMPORTED)
def test_not_imported_at_startup(imported, module):
    if module in IMPORTED_BY_THE_WINDOWS_CONSOLE \
            and 'win_unicode_console' in imported:
        pytest.skip('{} comes from win_unicode_console here'.format(module))

    assert module not in imported, (
        '{} is imported before a correction even starts; it used to be, and '
        'putting it back costs every invocation'.format(module))


def test_the_entry_point_still_works(imported):
    """Guards the guard: an import that failed would pass the test above."""
    assert 'thebleep.entrypoints.main' in imported
    assert 'thebleep.argument_parser' in imported


def test_correcting_is_what_pulls_the_rest_in(imported):
    """Starting up loads almost nothing; correcting loads what it needs."""
    assert 'thebleep.corrector' not in imported
    assert 'thebleep.shells' not in imported


class TestDispatch(object):
    """A command should only reach the rules that could possibly match it."""

    @pytest.fixture
    def entries(self, tmpdir, os_environ):
        os_environ['XDG_CACHE_HOME'] = str(tmpdir)
        from thebleep import corrector

        paths = corrector._rule_files(
            next(iter(corrector.get_rules_import_paths())))
        return rulepack.entries_for(paths)

    @pytest.mark.parametrize('script, output', [
        ('git brnch', "git: 'brnch' is not a git command."),
        ('puthon', 'command not found: puthon'),
        ('apt-get instal vim', 'E: Invalid operation instal'),
    ])
    def test_most_rules_are_skipped(self, entries, script, output):
        candidates = rulepack.candidate_entries(entries, Command(script,
                                                                 output))
        assert len(candidates) < len(entries) / 2, (
            'dispatch got broad again: {} of {} rules for {!r}'.format(
                len(candidates), len(entries), script))


class TestLargeOutput(object):
    """A command that printed a lot used to take seconds, twice over."""

    @pytest.fixture
    def big_output(self):
        return 'some line of build output\n' * 40000

    @pytest.fixture
    def noisy_process(self, tmpdir):
        """A real command printing far more than a pipe buffer holds.

        Started without a shell and with this interpreter, so the test says the
        same thing on every platform and owes nothing to quoting rules.

        """
        script_file = tmpdir.join('noisy.py')
        script_file.write("print('x' * 200000)")
        return subprocess.Popen(
            [sys.executable, str(script_file)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

    def test_reading_the_output_does_not_deadlock(self, noisy_process,
                                                  settings):
        """Reading only after the command exits hangs on a full pipe buffer.

        The process writes far more than a pipe holds, so if its output is not
        read while it runs, it never exits, and this waits out `wait_command`
        and comes back with nothing.

        """
        from thebleep.output_readers import rerun

        started = time.time()
        output = rerun._wait_output(noisy_process, False)
        took = time.time() - started

        assert output is not None, 'the output was lost to the timeout'
        assert len(output) > 100000, 'the output was truncated'
        assert took < settings.wait_command, (
            'took {:.1f}s of a {}s timeout, which means it waited for one'
            .format(took, settings.wait_command))

    def test_matching_a_big_output_is_not_quadratic(self, big_output):
        """One rule used to backtrack a character at a time over the whole
        output, which takes minutes on a megabyte."""
        from thebleep.rules import unknown_command

        command = Command('sh -c build', big_output)
        started = time.time()
        unknown_command.match(command)
        assert time.time() - started < 1.0

    def test_a_memoized_helper_does_not_copy_the_output(self, big_output):
        from thebleep import utils

        command = Command('git brnch', big_output)
        started = time.time()
        for _ in range(200):
            utils.is_app(command, 'git')
        assert time.time() - started < 0.5
