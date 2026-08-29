#!/usr/bin/env python3
"""Record commands and safe interface probes from a clean runner.

This is a discovery tool, not a test fixture generator.  Its output belongs in
the workflow artifact: hosted images change, and a moving PATH must not change
what the correction engine suggests in the hermetic test suite.
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import threading
import time


MAX_PROBE_OUTPUT = 64 * 1024
PROBE_TIMEOUT = 3.0

# These arguments either ask for version/help output or use an explicitly
# invalid option.  They must remain a small allowlist: probing every executable
# with --help is not read-only (some programs interpret it as a subcommand).
PROBES = {
    'awk': [['--version'], ['{']],
    'bash': [['--version']],
    'brew': [['--version']],
    'bun': [['--version']],
    'cargo': [['--version']],
    'choco': [['--version']],
    'cmake': [['--version']],
    'composer': [['--version']],
    'cp': [{'arguments': ['thebleep-source', 'missing-dir/destination'],
            'files': ['thebleep-source']},
           ['missing-source', 'destination']],
    'curl': [['--version']],
    'deno': [['--version']],
    'docker': [['--version']],
    'dotnet': [['--version']],
    'find': [['--version'], ['thebleep-inventory-no-such-path', '-name', '*']],
    'fish': [['--version']],
    'git': [['--version']],
    'go': [['version']],
    'grep': [['--version'], ['--definitely-not-a-bleep-option']],
    'hg': [['--version']],
    'ifconfig': [['thebleep-no-such-interface']],
    'java': [['-version']],
    'kubectl': [['version', '--client']],
    'ln': [{'arguments': ['-s', 'missing', 'existing'],
            'files': ['existing']}],
    'make': [['--version']],
    'mv': [{'arguments': ['thebleep-source', 'missing-dir/destination'],
            'files': ['thebleep-source']},
           ['missing-source', 'destination']],
    'mvn': [['--version']],
    'node': [['--version']],
    'npm': [['--version']],
    'nu': [['--version']],
    'perl': [['--version']],
    'php': [['--version']],
    'pip': [['--version']],
    'podman': [['--version']],
    'powershell': [['-NoProfile', '-Command',
                    '$PSVersionTable.PSVersion.ToString()']],
    'pwsh': [['-NoProfile', '-Command',
              '$PSVersionTable.PSVersion.ToString()']],
    'python': [['--version']],
    'python3': [['--version']],
    'ruby': [['--version']],
    'rustc': [['--version']],
    'sed': [['--version'], ['-e', 's/foo/bar']],
    'ssh': [['-V']],
    'svn': [['--version']],
    'tar': [['--version']],
    'terraform': [['version']],
    'tcsh': [['--version']],
    'uv': [['--version']],
    'winget': [['--version']],
    'yarn': [['--version']],
    'zsh': [['--version']],
}


def _path_entries():
    """Return the PATH entries, retaining their order and empty entries."""
    return os.environ.get('PATH', '').split(os.pathsep)


def _is_executable(path):
    try:
        if not path.is_file():
            return False
        if os.name == 'nt':
            suffixes = os.environ.get(
                'PATHEXT', '.COM;.EXE;.BAT;.CMD').lower().split(';')
            return path.suffix.lower() in suffixes
        return os.access(str(path), os.X_OK)
    except OSError:
        # Hosted runners contain protected system directories. They are still
        # valid PATH entries; one unreadable file must not lose the inventory.
        return False


def inventory_commands():
    """Return the first executable for each command visible through PATH."""
    commands = {}
    suffixes = ('.com', '.exe', '.bat', '.cmd') if os.name == 'nt' else ()
    for raw_directory in _path_entries():
        directory = Path(raw_directory or '.')
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except (OSError, RuntimeError):
            continue
        for path in entries:
            if not _is_executable(path):
                continue
            name = path.name
            if suffixes and path.suffix.lower() in suffixes:
                name = path.stem
            key = name.casefold() if os.name == 'nt' else name
            if key not in commands:
                commands[key] = {'name': name, 'path': str(path)}
    return sorted(commands.values(), key=lambda item: item['name'].casefold())


def _probe_output(process, output, finished, output_limited):
    """Read a child pipe without allowing an unbounded producer to hang us."""
    while True:
        chunk = process.stdout.read(4096)
        if not chunk:
            finished.set()
            return
        remaining = MAX_PROBE_OUTPUT - len(output)
        if remaining > 0:
            output.extend(chunk[:remaining])
        if len(chunk) > remaining:
            output_limited.set()
            finished.set()
            return


def run_probe(path, arguments, cwd, environment):
    """Run one allowlisted probe with a time and output bound."""
    started = time.monotonic()
    output = bytearray()
    finished = threading.Event()
    output_limited = threading.Event()
    try:
        process = subprocess.Popen(
            [path] + arguments,
            cwd=str(cwd),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL)
    except (OSError, ValueError) as error:
        return {'error': str(error), 'duration_ms': _duration(started)}

    reader = threading.Thread(
        target=_probe_output,
        args=(process, output, finished, output_limited), daemon=True)
    reader.start()
    timed_out = False
    deadline = started + PROBE_TIMEOUT
    while process.poll() is None:
        if output_limited.is_set():
            process.kill()
            break
        if time.monotonic() >= deadline:
            timed_out = True
            process.kill()
            break
        time.sleep(0.01)
    process.wait()
    reader.join(1)
    result = {
        'arguments': arguments,
        'returncode': process.returncode,
        'duration_ms': _duration(started),
        'output': bytes(output).decode('utf-8', 'replace'),
    }
    if timed_out:
        result['timeout'] = True
    if output_limited.is_set():
        result['output_truncated'] = True
    return result


def _duration(started):
    return round((time.monotonic() - started) * 1000, 1)


def probe_commands(commands):
    """Probe installed commands while isolating home/configuration files."""
    by_name = {item['name'].casefold(): item['path'] for item in commands}
    with tempfile.TemporaryDirectory(prefix='thebleep-inventory-') as home:
        environment = os.environ.copy()
        for variable in ('HOME', 'USERPROFILE', 'APPDATA', 'XDG_CONFIG_HOME'):
            environment[variable] = home
        results = []
        for name, argument_sets in sorted(PROBES.items()):
            path = by_name.get(name.casefold())
            if not path:
                continue
            for specification in argument_sets:
                if isinstance(specification, dict):
                    arguments = specification['arguments']
                    files = specification.get('files', ())
                else:
                    arguments, files = specification, ()
                with tempfile.TemporaryDirectory(
                        prefix='thebleep-probe-') as probe_directory:
                    for filename in files:
                        Path(probe_directory).joinpath(filename).touch()
                    probe_environment = environment.copy()
                    for variable in ('TMPDIR', 'TMP', 'TEMP'):
                        probe_environment[variable] = probe_directory
                    result = run_probe(
                        path, arguments, Path(probe_directory),
                        probe_environment)
                    result.update({'command': name, 'path': path})
                    results.append(result)
    return results


def build_inventory():
    commands = inventory_commands()
    return {
        'format': 1,
        'generated_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        'environment': {
            'runner_os': os.environ.get('RUNNER_OS'),
            'runner_image': os.environ.get('ImageOS'),
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'python': platform.python_version(),
            'shell': os.environ.get('SHELL') or os.environ.get('ComSpec'),
            'path_entries': _path_entries(),
        },
        'commands': commands,
        'probes': probe_commands(commands),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='command-inventory.json',
                        help='JSON path to write (default: %(default)s)')
    args = parser.parse_args()
    destination = Path(args.output)
    inventory = build_inventory()
    destination.write_text(json.dumps(inventory, indent=2, sort_keys=True) +
                           '\n', encoding='utf-8')
    print('recorded {} commands and {} probes in {}'.format(
        len(inventory['commands']), len(inventory['probes']), destination))


if __name__ == '__main__':
    main()
