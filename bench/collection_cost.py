#!/usr/bin/env python3
"""How long pytest spends collecting, and which imports own it.

The Windows job takes about five minutes where Linux takes seventy seconds, and
the shape of the output says where: nothing is printed for minutes, then the
progress dots arrive and run at roughly Linux speed to the end. pytest prints its
first progress line once collection is done, so the wait is collection --
importing 225 test modules -- and not the tests.

That makes it a one-time cost, not a per-test one, which is a different bug with
a different fix. This measures it directly and attributes it:

  * wall-clock for `--collect-only`, which is import plus collection and nothing
    else
  * the same again under `-X importtime`, which names everything the interpreter
    and pytest itself import
  * and per test file, from pytest's own collection hooks -- because pytest
    imports test modules through its assertion-rewriting loader, which
    `-X importtime` never sees

Prints a table and exits 0. Run on both platforms and compare.

    python bench/collection_cost.py
    python bench/collection_cost.py --json collection.json

"""

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Enough to see the shape without printing a thousand lines into a CI log.
TOP = 25

# `-X importtime` instruments the normal import machinery, and pytest does not
# use it for test modules: `_pytest.pathlib.import_path` builds the module and
# calls `exec_module` itself, so a test file that takes ten seconds to import
# leaves no trace there. Its own collection hooks do see it, so they are asked.
TIMER_PLUGIN = '''
import json
import os
import time

_started = {}
_durations = []


def pytest_collectstart(collector):
    _started[collector.nodeid] = time.perf_counter()


def pytest_collectreport(report):
    began = _started.pop(report.nodeid, None)
    if began is not None:
        _durations.append([round((time.perf_counter() - began) * 1000, 1),
                           report.nodeid])


def pytest_sessionfinish(session, exitstatus):
    # A file's time includes the classes and functions under it, which is what
    # "how long did this file cost" means.
    with open(os.environ['THEBLEEP_COLLECTION_JSON'], 'w') as handle:
        json.dump(sorted(_durations, reverse=True), handle)
'''


def _run(arguments, capture_stderr=False):
    started = time.perf_counter()
    finished = subprocess.run(
        [sys.executable] + arguments, cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if capture_stderr else subprocess.STDOUT)
    return (time.perf_counter() - started) * 1000, finished


def collected(output):
    """How many tests pytest said it found."""
    for line in reversed(output.splitlines()):
        if 'test' in line and ('collected' in line or 'tests collected' in line):
            return line.strip()
    return output.strip().splitlines()[-1] if output.strip() else ''


def importtime_rows(stderr):
    """Every module `-X importtime` reported, with its cumulative milliseconds.

    The cumulative column includes everything imported underneath, which is the
    number that says what not importing it would save.

    """
    rows = []
    for line in stderr.splitlines():
        if not line.startswith('import time:'):
            continue
        parts = line.split('|')
        if len(parts) != 3:
            continue
        try:
            cumulative = int(parts[1].strip())
        except ValueError:
            continue
        rows.append((cumulative / 1000.0, parts[2].strip()))
    return rows


def per_file():
    """How long each test file took to collect, slowest first."""
    directory = tempfile.mkdtemp(prefix='thebleep-collection-')
    plugin = os.path.join(directory, 'collection_timer.py')
    with open(plugin, 'w') as handle:
        handle.write(TIMER_PLUGIN)
    destination = os.path.join(directory, 'collection.json')

    environment = dict(os.environ, THEBLEEP_COLLECTION_JSON=destination)
    environment['PYTHONPATH'] = os.pathsep.join(
        [directory] + ([environment['PYTHONPATH']]
                       if environment.get('PYTHONPATH') else []))
    subprocess.run([sys.executable, '-m', 'pytest', '--collect-only', '-q',
                    '-p', 'collection_timer', 'tests'],
                   cwd=ROOT, env=environment,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        with open(destination) as handle:
            rows = json.load(handle)
    except (IOError, OSError, ValueError):
        return []
    # Files only: a directory's time is the sum of the files in it, and would be
    # counted twice.
    return [(ms, nodeid) for ms, nodeid in rows if nodeid.endswith('.py')]


def measure():
    # Bytecode caching makes the second collection a different measurement from
    # the first, and the first is the one a cold CI runner does.
    wall, finished = _run(['-m', 'pytest', '--collect-only', '-q', 'tests'])
    output = finished.stdout.decode('utf-8', 'replace')
    files = per_file()

    _, traced = _run(['-X', 'importtime', '-m', 'pytest', '--collect-only',
                      '-q', 'tests'], capture_stderr=True)
    rows = importtime_rows(traced.stderr.decode('utf-8', 'replace'))

    ours = [(ms, name) for ms, name in rows
            if name.startswith('thebleep') and name.count('.') <= 1]
    everything = sorted(rows, reverse=True)

    return {
        'platform': platform.platform(),
        'python': platform.python_version(),
        'collect_only_ms': round(wall, 1),
        'collected': collected(output),
        'modules_imported': len(rows),
        'thebleep_top_level_ms': round(sum(ms for ms, _ in ours), 1),
        'test_files_ms': round(sum(ms for ms, _ in files), 1),
        'test_files': len(files),
        'slowest_imports': [{'ms': round(ms, 1), 'module': name}
                            for ms, name in everything[:TOP]],
        'slowest_files': [{'ms': ms, 'file': nodeid}
                          for ms, nodeid in files[:TOP]],
    }


def report(numbers):
    for key in ('platform', 'python', 'collect_only_ms', 'collected',
                'modules_imported', 'test_files', 'test_files_ms',
                'thebleep_top_level_ms'):
        print('{:<24}  {}'.format(key, numbers[key]))

    print('\nslowest test files to collect, ms')
    for row in numbers['slowest_files']:
        print('  {:>8}  {}'.format(row['ms'], row['file']))

    print('\nslowest imports the interpreter and pytest do, cumulative ms')
    for row in numbers['slowest_imports']:
        print('  {:>8}  {}'.format(row['ms'], row['module']))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--json', help='also write the numbers to this file')
    args = parser.parse_args()

    numbers = measure()
    report(numbers)
    if args.json:
        with open(args.json, 'w') as handle:
            json.dump(numbers, handle, indent=2, sort_keys=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
