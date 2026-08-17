#!/usr/bin/env python3
"""Aggregates The Bleep's own debug timers into a phase breakdown.

`--debug` already wraps rule imports, rule matching and the command re-run in
`logs.debug_time`, so a single run carries a full accounting of where the time
went. This turns that firehose into a table, and adds the import graph cost
from `-X importtime` so startup and runtime are visible side by side.

Usage:

    ./bench/profile_phases.py --bin /path/to/venv/bin/thebleep
    ./bench/profile_phases.py --bin ... -- git brnch
    ./bench/profile_phases.py --bin ... --imports
"""

import argparse
import os
import re
import subprocess
import sys

TOOK = re.compile(r'(?P<what>.*?)took: 0:(?P<m>\d+):(?P<s>\d+\.\d+)')

PHASES = [
    ('rule imports', re.compile(r'Importing rule')),
    ('rule matching', re.compile(r'Trying rule')),
    ('command re-run', re.compile(r'^Call:')),
    ('read output log', re.compile(r'Read output from')),
]

TOTAL = re.compile(r'^Total')


def env_for(style='bleep', **extra):
    env = dict(os.environ)
    env.update({
        'TB_SHELL': 'bash',
        'TB_ALIAS': 'bleep',
        'TB_HISTORY': '',
        'THEBLEEP_DEBUG': 'true',
        'THEBLEEP_REQUIRE_CONFIRMATION': 'false',
        'PYTHONIOENCODING': 'utf-8',
    })
    env.update(extra)
    return env


def collect(binary, command):
    proc = subprocess.run([binary] + command, env=env_for(),
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return proc.stderr.decode('utf-8', 'replace')


def parse(debug_output):
    """Returns (phase totals in ms, event counts, total in ms)."""
    totals = {name: 0.0 for name, _ in PHASES}
    counts = {name: 0 for name, _ in PHASES}
    grand = None
    for line in debug_output.splitlines():
        line = line.strip()
        if not line.startswith('DEBUG:'):
            continue
        body = line[len('DEBUG:'):].strip()
        match = TOOK.search(body)
        if not match:
            continue
        millis = (int(match.group('m')) * 60 + float(match.group('s'))) * 1000
        what = match.group('what')
        if TOTAL.match(what):
            grand = millis
            continue
        for name, pattern in PHASES:
            if pattern.search(what):
                totals[name] += millis
                counts[name] += 1
                break
    return totals, counts, grand


def import_cost(binary):
    """Cumulative import time of the entry point, via -X importtime."""
    python = os.path.join(os.path.dirname(binary), 'python')
    if not os.path.exists(python):
        python = sys.executable
    proc = subprocess.run(
        [python, '-X', 'importtime', '-c',
         'import thebleep.entrypoints.main'],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env_for())
    lines = proc.stderr.decode('utf-8', 'replace').splitlines()
    per_module = {}
    for line in lines:
        parts = line.split('|')
        if len(parts) != 3:
            continue
        try:
            cumulative = float(parts[1].strip()) / 1000.0
        except ValueError:
            continue
        per_module[parts[2].strip()] = cumulative
    return per_module


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--bin', required=True, help='thebleep executable')
    parser.add_argument('--imports', action='store_true',
                        help='also break down the import graph')
    parser.add_argument('--repeat', type=int, default=3,
                        help='runs to average over')
    parser.add_argument('command', nargs='*', default=None,
                        help='command to correct (default: git brnch)')
    args = parser.parse_args()

    command = args.command or ['git', 'brnch']

    runs = []
    for _ in range(args.repeat):
        runs.append(parse(collect(args.bin, command)))

    print('# phase breakdown of `{} {}`  ({} runs, median)'.format(
        os.path.basename(args.bin), ' '.join(command), args.repeat))
    print()
    print('{:20}{:>12}{:>10}'.format('phase', 'time', 'events'))
    print('-' * 42)

    def median(values):
        values = sorted(values)
        return values[len(values) // 2]

    for name, _ in PHASES:
        times = [run[0][name] for run in runs]
        events = [run[1][name] for run in runs]
        if not any(events):
            continue
        print('{:20}{:>12}{:>10}'.format(
            name, '{:.1f} ms'.format(median(times)), median(events)))

    grands = [run[2] for run in runs if run[2] is not None]
    if grands:
        accounted = sum(median([run[0][name] for run in runs])
                        for name, _ in PHASES)
        print('{:20}{:>12}{:>10}'.format(
            'unaccounted', '{:.1f} ms'.format(median(grands) - accounted), ''))
        print('-' * 42)
        print('{:20}{:>12}'.format('in-process total',
                                   '{:.1f} ms'.format(median(grands))))

    if args.imports:
        modules = import_cost(args.bin)
        print()
        print('# import graph, cumulative per subtree')
        print()
        interesting = ['thebleep.entrypoints.main', 'thebleep.shells',
                       'thebleep.types', 'thebleep.utils', 'pyte', 'psutil',
                       'colorama', 'decorator', 'site']
        for name in interesting:
            if name in modules:
                print('{:32}{:>10}'.format(
                    name, '{:.1f} ms'.format(modules[name])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
