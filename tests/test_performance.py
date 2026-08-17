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


def _imported_modules(env=None):
    """Everything imported by loading the entry point, in a fresh process."""
    source = textwrap.dedent('''
        import sys
        import thebleep.entrypoints.main   # noqa: F401
        print('\\n'.join(sorted(sys.modules)))
    ''')
    environment = dict(os.environ)
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

    def test_reading_the_output_does_not_deadlock(self):
        """Reading only after the command exits hangs on a full pipe buffer.

        The command below writes far more than a pipe holds, so if the output
        is not read while it runs, this waits out `wait_command` and returns
        nothing.

        """
        from thebleep.conf import settings
        from thebleep.output_readers import rerun

        settings.init()
        script = 'yes abcdefghijklmnopqrstuvwxyz | head -n 40000'
        started = time.time()
        output = rerun.get_output(script, script)
        took = time.time() - started

        assert output is not None, 'the output was lost'
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
