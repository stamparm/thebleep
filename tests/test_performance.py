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
    'shelve',      # nothing keeps a cache this way any more
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


# The same question asked of a whole correction rather than of startup. Each of
# these used to be imported to correct `ehco hello`, and none of them was used
# doing it. They are named individually rather than counted because a name is
# what a future change will put back, and because several are C extensions --
# on Windows a `.pyd` is read by the virus scanner before it can be mapped,
# which makes it the most expensive kind of module there is.
NOT_NEEDED_TO_CORRECT = [
    'ast',            # only to read a rule the compiled pack does not have
    'pickle',         # only for a memoized call whose arguments cannot be hashed
    'socket',         # only when a shell logger is listening
    'mmap',           # only instant mode, reading the recorded session
    'uuid',           # only instant mode's alias
    'platform',       # dragged in by uuid
    'tempfile',       # only instant mode's alias, and the no-home fallback
    'shutil',         # `which` does the lookup itself now
    'bz2',            # dragged in by shutil
    'lzma',           # dragged in by shutil
    'zlib',           # dragged in by shutil
    'colorama',       # only when colour is actually written, and it brings
                      # `ctypes` -- a DLL the scanner reads before it maps it
]

# How many modules a whole correction costs beyond what the interpreter has
# open before it runs a line. A difference rather than a count, because the
# baseline moves between Python versions and this has to mean the same thing on
# every one of them. Measured on 3.11: 81 before the startup work, 42 after it
# from an installed wheel and 47 from a checkout, which carries the editable
# install's own finder. The ceiling leaves room for a module added on purpose,
# and for the standard library rearranging itself between releases, and none to
# drift back to where this started.
IMPORT_BUDGET = 60


def _correction_modules(tmp_path):
    """Everything imported by correcting a command, in a fresh process.

    The list goes to a file rather than to a stream, because a correction
    writes the suggestion to one and its own logging to the other, and a module
    list with `echo` and `hello` in it is not a module list.

    """
    source = textwrap.dedent('''
        import sys
        sys.argv = ['thebleep', '--yes', '--', 'ehco', 'hello']
        from thebleep.entrypoints.main import main
        try:
            main()
        except SystemExit:
            pass
        with open(sys.argv[0] + '.modules', 'w') as handle:
            handle.write('\\n'.join(sorted(sys.modules)))
    ''')
    environment = dict(REAL_ENVIRONMENT, TB_SHELL='bash')
    listing = str(tmp_path) + '.modules'
    source = source.replace("sys.argv[0] + '.modules'", repr(listing))
    # Twice, and the second one is the measurement. The first correction on a
    # machine finds no compiled rule pack and has to build one, which means
    # reading every rule from source and so importing `ast`; every correction
    # after it unmarshals the pack instead. Measuring the first would be
    # measuring an installation, which happens once and is not what anybody
    # waits for.
    for _ in range(2):
        subprocess.run([sys.executable, '-c', source], env=environment,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(listing) as handle:
        return set(handle.read().split())


def _baseline_modules():
    """What the interpreter has open before any of our code runs."""
    result = subprocess.run(
        [sys.executable, '-c', 'import sys; print(len(sys.modules))'],
        stdout=subprocess.PIPE, env=dict(REAL_ENVIRONMENT))
    return int(result.stdout)


@pytest.fixture(scope='module')
def corrected(tmp_path_factory):
    return _correction_modules(tmp_path_factory.mktemp('imports') / 'run')


@pytest.mark.parametrize('module', NOT_NEEDED_TO_CORRECT)
def test_not_imported_by_a_correction(corrected, module):
    assert module not in corrected, (
        '{} is imported to correct a command and is not used doing it; each '
        'one is a file the interpreter has to find and open, and on Windows '
        'that is most of what a correction costs'.format(module))


def test_a_correction_stays_within_its_import_budget(corrected):
    """Guards the whole of it, not just the modules named above."""
    assert 'thebleep.corrector' in corrected, 'the correction did not run'

    marginal = len(corrected) - _baseline_modules()
    assert marginal <= IMPORT_BUDGET, (
        'correcting a command imports {} modules beyond a bare interpreter, '
        'and the budget is {}'.format(marginal, IMPORT_BUDGET))


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
