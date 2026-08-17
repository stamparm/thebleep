#!/usr/bin/env python3
"""Latency harness for The Bleep.

Runs a fixed set of scenarios against one or more subjects (an installed
`thebleep`, an installed `thefuck` for the upstream baseline, or any other
executable) and reports wall-clock statistics.

The harness shells out to `hyperfine` when it is available, because its
statistics and warmup handling are better than anything worth reimplementing.
Without hyperfine it falls back to its own timing loop, which reports the same
numbers so results stay comparable.

Usage:

    ./bench/bench.py --subject bleep=/path/to/venv/bin/thebleep
    ./bench/bench.py --subject bleep=... --subject fuck=... --json out.json
    ./bench/bench.py --list
    ./bench/bench.py --scenario correct-fast --runs 30
    ./bench/bench.py --baseline before.json          # compare against a run

Every scenario is a name, a command template and the environment it needs.
`{bin}` in a command is replaced with the subject's executable.
"""

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Scenario definitions ------------------------------------------------------
#
# `env_style` picks the environment variable prefix, since the subject may be
# either The Bleep (TB_/THEBLEEP_) or upstream The Fuck (TF_/THEFUCK_).


def _env(style, **kwargs):
    """Builds scenario env for the `bleep` or `fuck` naming of a variable."""
    prefixes = {'bleep': ('TB_', 'THEBLEEP_'), 'fuck': ('TF_', 'THEFUCK_')}
    short, long_ = prefixes[style]
    out = {}
    for key, value in kwargs.items():
        if key.isupper():
            out[long_ + key] = value
        else:
            out[short + key.upper()] = value
    return out


SCENARIOS = [
    {
        'name': 'alias',
        'what': 'generate the shell alias (paid at every shell startup)',
        'args': ['--alias'],
        'env': lambda style: _env(style, shell='bash'),
    },
    {
        'name': 'version',
        'what': 'interpreter start plus the import graph, no rules',
        'args': ['--version'],
        'env': lambda style: _env(style, shell='bash'),
    },
    {
        'name': 'correct-fast',
        'what': 'correct a mistyped git command that fails instantly',
        'args': ['git', 'brnch'],
        'env': lambda style: _env(style, shell='bash', alias='bleep',
                                  REQUIRE_CONFIRMATION='false'),
    },
    {
        'name': 'correct-nomatch',
        'what': 'no rule matches, so every rule is consulted',
        'args': ['--force-command', 'zzzzz_no_such_command_zzzzz'],
        'env': lambda style: _env(style, shell='bash', alias='bleep',
                                  history='', REQUIRE_CONFIRMATION='false'),
    },
    {
        'name': 'correct-slow',
        'what': 'the failed command takes 500ms to re-run',
        'args': ['--force-command', 'sh -c "sleep 0.5; exit 1"'],
        'env': lambda style: _env(style, shell='bash', alias='bleep',
                                  history='', REQUIRE_CONFIRMATION='false'),
    },
    {
        'name': 'correct-big-output',
        'what': 'the failed command printed a megabyte, as builds do',
        'args': ['--force-command',
                 'sh -c "yes abcdefghijklmnopqrstuvwxyz | head -n 40000; exit 1"'],
        'env': lambda style: _env(style, shell='bash', alias='bleep',
                                  history='', REQUIRE_CONFIRMATION='false'),
    },
    {
        'name': 'correct-in-repo',
        'what': 'correct inside a git repository, where git rules do work',
        'args': ['git', 'stats'],
        'env': lambda style: _env(style, shell='bash', alias='bleep',
                                  REQUIRE_CONFIRMATION='false'),
        'cwd': ROOT,
    },
]

SCENARIOS_BY_NAME = {s['name']: s for s in SCENARIOS}


def scenario_env(scenario, style):
    """Full environment for a scenario: a clean base plus scenario specifics."""
    env = {
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'HOME': os.environ.get('HOME', '/root'),
        'LC_ALL': 'C',
        'LANG': 'C',
        'PYTHONIOENCODING': 'utf-8',
    }
    for keep in ('XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME',
                 'PYTHONPATH', 'VIRTUAL_ENV'):
        if keep in os.environ:
            env[keep] = os.environ[keep]
    env.update(scenario['env'](style))
    return env


# Timing -------------------------------------------------------------------


def have_hyperfine():
    return shutil.which('hyperfine') is not None


def run_once(argv, env, cwd, cpu=None):
    """Runs the command once, returns wall-clock milliseconds."""
    if cpu:
        argv = ['taskset', '-c', cpu] + argv
    started = time.perf_counter()
    subprocess.call(argv, env=env, cwd=cwd,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (time.perf_counter() - started) * 1000.0


def summarize(samples):
    samples = sorted(samples)
    return {
        'runs': len(samples),
        'min': round(samples[0], 2),
        'median': round(statistics.median(samples), 2),
        'mean': round(statistics.mean(samples), 2),
        'stddev': round(statistics.pstdev(samples), 2) if len(samples) > 1 else 0.0,
        'max': round(samples[-1], 2),
        'p95': round(samples[min(len(samples) - 1, int(len(samples) * 0.95))], 2),
    }


def measure_builtin(argv, env, cwd, runs, warmup, cpu):
    for _ in range(warmup):
        run_once(argv, env, cwd, cpu)
    return summarize([run_once(argv, env, cwd, cpu) for _ in range(runs)])


def measure_hyperfine(argv, env, cwd, runs, warmup, cpu):
    """Delegates to hyperfine and translates its JSON export."""
    if cpu:
        argv = ['taskset', '-c', cpu] + argv
    command = ' '.join(_quote(a) for a in argv)
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        export = tmp.name
    try:
        proc = subprocess.run(
            ['hyperfine', '--style', 'none', '--warmup', str(warmup),
             '--runs', str(runs), '--export-json', export,
             '--ignore-failure', command],
            env=env, cwd=cwd,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode('utf-8', 'replace').strip())
        with open(export) as handle:
            result = json.load(handle)['results'][0]
        samples = [t * 1000.0 for t in result['times']]
        out = summarize(samples)
        out['tool'] = 'hyperfine'
        return out
    finally:
        os.path.exists(export) and os.unlink(export)


def _quote(arg):
    if not arg or any(c in arg for c in ' \t"\'$`\\'):
        return "'" + arg.replace("'", "'\\''") + "'"
    return arg


# Driver -------------------------------------------------------------------


def parse_subject(spec):
    """`name=/path/to/bin[:style]` -> dict."""
    if '=' not in spec:
        raise argparse.ArgumentTypeError(
            'subject must look like name=/path/to/executable')
    name, path = spec.split('=', 1)
    # Absolute, because scenarios run from a directory of their choosing.
    path = os.path.abspath(os.path.expanduser(path))
    style = 'fuck' if 'fuck' in os.path.basename(path) else 'bleep'
    return {'name': name, 'bin': path, 'style': style}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--subject', action='append', type=parse_subject,
                        default=[], metavar='NAME=PATH',
                        help='executable to measure, repeatable')
    parser.add_argument('--scenario', action='append', default=[],
                        help='limit to these scenarios, repeatable')
    parser.add_argument('--runs', type=int, default=20)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--cpu', default=os.environ.get('BENCH_CPU', ''),
                        help='pin to these CPUs via taskset, e.g. 2,3')
    parser.add_argument('--json', help='write results to this file')
    parser.add_argument('--baseline', help='compare against an earlier --json')
    parser.add_argument('--list', action='store_true',
                        help='list scenarios and exit')
    parser.add_argument('--no-hyperfine', action='store_true')
    args = parser.parse_args()

    if args.list:
        for scenario in SCENARIOS:
            print('{:16} {}'.format(scenario['name'], scenario['what']))
        return 0

    if not args.subject:
        parser.error('at least one --subject is required')

    scenarios = [SCENARIOS_BY_NAME[name] for name in args.scenario] \
        if args.scenario else SCENARIOS

    measure = measure_builtin
    tool = 'builtin'
    if have_hyperfine() and not args.no_hyperfine:
        measure, tool = measure_hyperfine, 'hyperfine'

    print('# The Bleep latency harness')
    print('# timer: {}   runs: {}   warmup: {}   pinned: {}'.format(
        tool, args.runs, args.warmup, args.cpu or 'no'))
    print()

    results = {'tool': tool, 'runs': args.runs, 'subjects': {}}
    for subject in args.subject:
        if not os.path.exists(subject['bin']):
            print('! missing subject {}: {}'.format(
                subject['name'], subject['bin']), file=sys.stderr)
            continue
        results['subjects'][subject['name']] = {
            'bin': subject['bin'], 'scenarios': {}}
        for scenario in scenarios:
            argv = [subject['bin']] + scenario['args']
            env = scenario_env(scenario, subject['style'])
            cwd = scenario.get('cwd', tempfile.gettempdir())
            try:
                stats = measure(argv, env, cwd,
                                args.runs, args.warmup, args.cpu)
            except Exception as exc:                     # noqa: BLE001
                print('! {}/{} failed: {}'.format(
                    subject['name'], scenario['name'], exc), file=sys.stderr)
                continue
            results['subjects'][subject['name']]['scenarios'][
                scenario['name']] = stats

    report(results, args.baseline)

    if args.json:
        directory = os.path.dirname(os.path.abspath(args.json))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.json, 'w') as handle:
            json.dump(results, handle, indent=2, sort_keys=True)
        print('\nwrote {}'.format(args.json))
    return 0


def report(results, baseline_path=None):
    baseline = None
    if baseline_path:
        with open(baseline_path) as handle:
            baseline = json.load(handle)

    names = list(results['subjects'])
    head = '{:16}'.format('scenario')
    for name in names:
        head += '{:>14}'.format(name)
    if len(names) == 2:
        head += '{:>10}'.format('ratio')
    if baseline:
        # The subject under test is the last one given; comparing the upstream
        # baseline against itself would say nothing.
        head += '{:>12}'.format('vs base')
    print(head)
    print('-' * len(head))

    scenario_names = []
    for name in names:
        for scenario in results['subjects'][name]['scenarios']:
            if scenario not in scenario_names:
                scenario_names.append(scenario)

    for scenario in scenario_names:
        line = '{:16}'.format(scenario)
        medians = []
        for name in names:
            stats = results['subjects'][name]['scenarios'].get(scenario)
            if not stats:
                line += '{:>14}'.format('-')
                medians.append(None)
                continue
            line += '{:>14}'.format('{} ms'.format(stats['median']))
            medians.append(stats['median'])
        if len(names) == 2 and all(medians):
            line += '{:>10}'.format('{:.2f}x'.format(medians[0] / medians[1])
                                    if medians[1] else '-')
        if baseline:
            line += '{:>12}'.format(_delta(baseline, names[-1], scenario,
                                           medians[-1]))
        print(line)


def _delta(baseline, subject, scenario, now):
    try:
        was = baseline['subjects'][subject]['scenarios'][scenario]['median']
    except (KeyError, TypeError):
        return '-'
    if not was or now is None:
        return '-'
    change = (now - was) / was * 100.0
    return '{:+.1f}%'.format(change)


if __name__ == '__main__':
    sys.exit(main())
