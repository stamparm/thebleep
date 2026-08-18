#!/usr/bin/env python3
"""Which phase of a correction the time is actually in, on this platform.

A correction on Windows costs about five times what it costs on Linux, and the
whole-invocation numbers in `bench/bench.py` do not say which part. This splits
one invocation into the four things it is made of and prints each, so the answer
is a number instead of an opinion:

  * starting an interpreter at all, with nothing imported
  * importing what the entry point needs
  * loading the rules -- and whether the pack is being rebuilt every run, which
    would be a bug rather than a platform tax
  * spawning a shell, which is what re-running the failed command costs

Prints a table and exits 0 whatever it finds. Run it on both platforms and
compare; a single machine's numbers mean nothing on their own.

    python bench/where_time_goes.py
    python bench/where_time_goes.py --json phases.json

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

RUNS = 5

# Two runs against one cache directory. The first is allowed to build the pack;
# if the second builds anything at all, the cache is not being reused, and that
# is the whole 74 ms of "loading the rules" explained by a bug.
PACK_DRIVER = r'''
import json
import sys
from thebleep import conf, rulepack
conf.settings.init()

built = []
real = rulepack._build_entry
rulepack._build_entry = lambda *a, **k: (built.append(1), real(*a, **k))[1]

from thebleep.corrector import get_corrected_commands
from thebleep.types import Command

started = __import__('time').perf_counter()
corrections = list(get_corrected_commands(
    Command(u'git brnch', u"git: 'brnch' is not a git command")))
took = (__import__('time').perf_counter() - started) * 1000

path = rulepack._cache_path()
json.dump({'built': len(built), 'corrections': len(corrections),
           'pack': str(path), 'pack_exists': path.is_file(),
           'correcting_ms': round(took, 1)}, sys.stdout)
'''


def fastest(call):
    """The quickest of `RUNS` attempts, in milliseconds.

    The quickest rather than the mean: everything that makes a run slower than
    its floor -- a scheduler, a scanner, another job on the runner -- is noise
    on top of the thing being measured.

    """
    best = None
    for _ in range(RUNS):
        started = time.perf_counter()
        call()
        took = (time.perf_counter() - started) * 1000
        best = took if best is None else min(best, took)
    return best


def _python(*arguments, **kwargs):
    subprocess.run([sys.executable] + list(arguments),
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   cwd=ROOT, **kwargs)


def importtime(module, count=10):
    """The `count` slowest imports pulled in by `module`, cumulative ms.

    `-X importtime` reports one line per module with its own time and the time
    of everything under it; the cumulative column is the one that says what
    dropping an import would save.

    """
    finished = subprocess.run(
        [sys.executable, '-X', 'importtime', '-c',
         'import {}'.format(module)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
    rows = []
    for line in finished.stderr.decode('utf-8', 'replace').splitlines():
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
    rows.sort(reverse=True)
    # Anything whose name contains a dot is a submodule of something already
    # listed, so keeping only top-level names stops the same time being read
    # several times over.
    top = [(ms, name) for ms, name in rows if '.' not in name]
    return [{'ms': round(ms, 1), 'module': name} for ms, name in top[:count]]


def pack_behaviour():
    """Whether a second run reuses the pack the first one wrote."""
    driver = os.path.join(tempfile.mkdtemp(prefix='thebleep-phases-'),
                          'driver.py')
    with open(driver, 'w') as handle:
        handle.write(PACK_DRIVER)

    cache = tempfile.mkdtemp(prefix='thebleep-cache-')
    environment = dict(os.environ, XDG_CACHE_HOME=cache,
                       PYTHONPATH=ROOT)

    runs = []
    for _ in range(2):
        finished = subprocess.run([sys.executable, driver], env=environment,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=ROOT)
        try:
            runs.append(json.loads(finished.stdout.decode('utf-8')))
        except ValueError:
            runs.append({'error': finished.stderr.decode(
                'utf-8', 'replace')[-600:]})
    return runs


def shell_spawn():
    """What re-running the failed command costs before it does anything.

    `replay` hands the script to a shell, so every correction that reads the
    previous command's output pays one `CreateProcess` or one `fork`.

    """
    script = 'exit 1'

    def once():
        process = subprocess.Popen(script, shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        process.communicate()

    return fastest(once)


def measure():
    bare = fastest(lambda: _python('-c', 'pass'))
    imported = fastest(lambda: _python('-c', 'import thebleep.main'))
    # What the `thebleep` console script itself imports, which is the number
    # that matters: `thebleep.main` is only the argument parsing.
    entry = fastest(lambda: _python('-c',
                                    'import thebleep.entrypoints.main'))
    runs = pack_behaviour()

    return {
        'platform': platform.platform(),
        'python': platform.python_version(),
        'interpreter_ms': round(bare, 1),
        'import_thebleep_ms': round(imported - bare, 1),
        'import_entrypoint_ms': round(entry - bare, 1),
        'shell_spawn_ms': round(shell_spawn(), 1),
        'slowest_imports': importtime('thebleep.entrypoints.main'),
        'pack_first_run': runs[0],
        'pack_second_run': runs[1],
    }


def report(numbers):
    for key in ('platform', 'python', 'interpreter_ms', 'import_thebleep_ms',
                'import_entrypoint_ms', 'shell_spawn_ms'):
        print('{:<22}  {}'.format(key, numbers[key]))

    print('\nslowest imports (cumulative ms)')
    for row in numbers['slowest_imports']:
        print('  {:>7}  {}'.format(row['ms'], row['module']))

    print('\nrule pack')
    for name in ('pack_first_run', 'pack_second_run'):
        print('  {:<16} {}'.format(name.replace('pack_', ''), numbers[name]))

    second = numbers['pack_second_run']
    if second.get('built'):
        print('\n  A second run rebuilt {} entries. The pack is not being '
              'reused, and that is a bug, not a platform cost.'
              .format(second['built']))


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
