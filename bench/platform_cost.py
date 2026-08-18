#!/usr/bin/env python3
"""Which kind of work this platform is slow at: computing, or touching files.

The suite takes about 4.5 times as long on Windows as on Linux -- roughly 260
seconds more for the same 3054 tests, which is about 85 ms per test. Only
something paid once per test can add up to that, and the candidates were
guessable but not distinguishable from the whole-suite number: a slower machine,
process creation, or the filesystem.

So each is measured on its own, with nothing else in the way, and the ratios
between platforms decide it:

  * `cpu` -- arithmetic in a loop. No syscalls, no allocation to speak of.
  * `files` -- create, write, stat, read and delete many small files, which is
    what a test using `tmpdir` and a settings file does.
  * `imports` -- reading and executing many modules, the shape of collection.
  * `spawn` -- starting a process through a shell, which is what re-running a
    failed command costs.

They cannot all be slow for the same reason. If `cpu` comes back at parity and
`files` at four times, the answer is the filesystem, and on Windows that means a
scanner in front of every open. If `cpu` is itself four times, it is just a
slower machine and there is nothing here to fix.

Prints a table and exits 0. Run on both platforms; one machine's numbers say
nothing.

    python bench/platform_cost.py
    python bench/platform_cost.py --json cost.json

"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

FILES = 2000
LOOPS = 3_000_000
SPAWNS = 20
MODULES = 200


def fastest(call, attempts=3):
    """The quickest attempt, in milliseconds.

    The floor, not the mean: anything above it is another process on the runner,
    not the work being measured.

    """
    best = None
    for _ in range(attempts):
        started = time.perf_counter()
        call()
        took = (time.perf_counter() - started) * 1000
        best = took if best is None else min(best, took)
    return best


def cpu():
    """Arithmetic and nothing else."""
    def once():
        total = 0
        for number in range(LOOPS):
            total += number * number
        return total

    return fastest(once)


def files():
    """A small file's whole life, `FILES` times over.

    Create, write, close, stat, read back, delete -- every one of which is a
    separate open on Windows, and every open is what a scanner sits in front of.

    """
    def once():
        directory = tempfile.mkdtemp(prefix='thebleep-files-')
        try:
            for index in range(FILES):
                path = os.path.join(directory, 'f{}'.format(index))
                with open(path, 'w') as handle:
                    handle.write('x' * 200)
                os.stat(path)
                with open(path) as handle:
                    handle.read()
                os.unlink(path)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    return fastest(once, attempts=2)


def imports():
    """Reading and executing `MODULES` modules, which is what collection does.

    Written out and imported rather than importing the real suite, so the number
    is about the platform and not about what we happen to import today. Bytecode
    is left uncached -- the interesting case is the first read of a file, which
    is the case collection is in.

    """
    directory = tempfile.mkdtemp(prefix='thebleep-imports-')
    for index in range(MODULES):
        with open(os.path.join(directory, 'm{}.py'.format(index)),
                  'w') as handle:
            handle.write('VALUE = {}\n'.format(index))

    script = ('import sys\n'
              'sys.dont_write_bytecode = True\n'
              'sys.path.insert(0, {!r})\n'
              'for index in range({}):\n'
              '    __import__("m{{}}".format(index))\n').format(directory,
                                                                MODULES)

    def once():
        subprocess.run([sys.executable, '-c', script],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        # Minus one interpreter start, which is measured separately and is not
        # what this is about.
        bare = fastest(lambda: subprocess.run(
            [sys.executable, '-c', 'pass'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        return fastest(once) - bare
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def spawn():
    """Starting a process through a shell, `SPAWNS` times."""
    def once():
        for _ in range(SPAWNS):
            process = subprocess.Popen('exit 1', shell=True,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            process.communicate()

    return fastest(once, attempts=2) / SPAWNS


def measure():
    return {
        'platform': platform.platform(),
        'python': platform.python_version(),
        'cpu_ms': round(cpu(), 1),
        'files_ms': round(files(), 1),
        'imports_ms': round(imports(), 1),
        'spawn_ms': round(spawn(), 2),
        'files_count': FILES,
        'cpu_loops': LOOPS,
        'modules': MODULES,
    }


def report(numbers):
    print('{:<20}  {}'.format('platform', numbers['platform']))
    print('{:<20}  {}'.format('python', numbers['python']))
    print('')
    print('{:<20}  {:>10}  {}'.format('what', 'ms', 'per unit'))
    print('-' * 52)
    print('{:<20}  {:>10}  {}'.format(
        'cpu', numbers['cpu_ms'],
        '{:.0f} ns/loop'.format(numbers['cpu_ms'] * 1e6 / LOOPS)))
    print('{:<20}  {:>10}  {}'.format(
        'files', numbers['files_ms'],
        '{:.0f} us/file'.format(numbers['files_ms'] * 1000 / FILES)))
    print('{:<20}  {:>10}  {}'.format(
        'imports', numbers['imports_ms'],
        '{:.0f} us/module'.format(numbers['imports_ms'] * 1000 / MODULES)))
    print('{:<20}  {:>10}  {}'.format('spawn', numbers['spawn_ms'],
                                      'per process'))
    print('')
    print('Compare each line against the other platform. `cpu` is the machine, '
          '`files` is the filesystem, and they cannot both explain the same '
          'gap.')


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
