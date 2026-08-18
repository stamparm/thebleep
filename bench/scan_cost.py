#!/usr/bin/env python3
"""What looking for a command costs, and how much of that is $PATH.

`no_command` is the commonest correction there is, and to make one it compares
the typo against every executable on $PATH: list every directory on it, and ask
of every entry whether it could be run. On Linux that is a few thousand cheap
syscalls. Windows has been reported as slow, and this is the first thing to rule
in or out -- NTFS with a virus scanner in front of every file, `System32` and
`WindowsApps`, and PATHEXT deciding instead of one `access` call.

Prints a table and exits 0 whatever it finds. This is a measurement, not a gate:
a hosted runner is far too noisy to fail a build on, and it is the comparison
between platforms that means something, not any single number.

    python bench/scan_cost.py
    python bench/scan_cost.py --json cost.json

"""

import argparse
import json
import os
import platform
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thebleep import cachefile, conf, utils              # noqa: E402


def timed(call):
    """`call`'s result, and how many milliseconds it took."""
    started = time.perf_counter()
    result = call()
    return (time.perf_counter() - started) * 1000, result


def _names(path):
    try:
        return os.listdir(path)
    except OSError:
        return []


def inventory(paths):
    """How many of `paths` are really there, and how many entries they hold."""
    directories = 0
    entries = 0
    for path in paths:
        names = _names(path)
        if not os.path.isdir(path):
            continue
        directories += 1
        entries += len(names)
    return directories, entries


def measure():
    conf.settings.init()
    paths = utils._search_path()
    directories, entries = inventory(paths)

    # Cold means what a user pays the first time, and after anything is
    # installed: the on-disk listing is keyed on the directories' timestamps.
    cachefile.clear()
    cold, found = timed(lambda: utils._scan_executables(paths, ()))
    warm, _ = timed(lambda: utils._scan_executables(paths, ()))

    # What the scan is actually made of, one entry at a time, so a slow
    # filesystem can be told apart from a lot of files.
    extensions = utils._executable_extensions()
    per_entry = None
    biggest = max(paths, key=lambda path: len(_names(path)), default=None)
    if biggest:
        names = _names(biggest)
        if names:
            probe, _ = timed(
                lambda: [utils._is_invocable(entry, extensions)
                         for entry in os.scandir(biggest)])
            per_entry = probe * 1000 / len(names)

    return {
        'platform': platform.platform(),
        'python': platform.python_version(),
        'path_entries': len(paths),
        'path_directories_present': directories,
        'files_on_path': entries,
        'commands_found': len(found),
        'pathext': os.environ.get('PATHEXT', ''),
        'cold_scan_ms': round(cold, 1),
        'warm_scan_ms': round(warm, 1),
        'per_entry_us': None if per_entry is None else round(per_entry, 2),
        'biggest_directory': biggest,
    }


def report(numbers):
    width = max(len(key) for key in numbers)
    for key, value in numbers.items():
        print('{:<{}}  {}'.format(key, width, value))

    cold = numbers['cold_scan_ms']
    warm = numbers['warm_scan_ms']
    print('')
    print('A first correction pays {:.0f} ms of this; every one after it pays '
          '{:.0f} ms until something on $PATH changes.'.format(cold, warm))


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
