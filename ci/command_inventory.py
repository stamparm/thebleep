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
import shutil
import subprocess
import sys
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
    # Keep native Windows command-not-found wording in the artifact. These
    # probes are harmless and only run where the corresponding executables
    # exist; the unique name avoids colliding with a real command on PATH.
    'cmd': [['/d', '/c', 'thebleep-inventory-no-such-command']],
    'cp': [{'arguments': ['thebleep-source', 'missing-dir/destination'],
            'files': ['thebleep-source'],
            'checks': ['cp_create_destination']},
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
    'ls': [{'arguments': ['--definitely-not-a-bleep-option'],
            'platforms': ('Darwin', 'Linux')}],
    'make': [['--version']],
    'mkdir': [{'arguments': ['missing-dir/destination'],
               'checks': ['mkdir_p'],
               'diagnoses': ['missing_path']}],
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
    'powershell': [
        ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()'],
        ['-NoProfile', '-Command', 'thebleep-inventory-no-such-command']],
    'pwsh': [
        ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()'],
        ['-NoProfile', '-Command', 'thebleep-inventory-no-such-command']],
    'python': [['--version']],
    'python3': [['--version']],
    'ruby': [['--version']],
    'rustc': [['--version']],
    'sed': [['--version'], {'arguments': ['-e', 's/foo/bar'],
                            'checks': ['sed_unterminated_s']}],
    'ssh': [['-V']],
    'svn': [['--version']],
    'tar': [['--version']],
    'touch': [{'arguments': ['missing-dir/file'], 'checks': ['touch']}],
    'terraform': [['version']],
    'tcsh': [['--version']],
    'uv': [['--version']],
    'winget': [['--version']],
    'yarn': [['--version']],
    'zsh': [['--version']],
    'zypper': [['--version'],
               {'arguments': ['isntall', 'vim'],
                'checks': ['zypper_no_such_command'],
                'helper_checks': True}],
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


class _TemporaryDirectory:
    """Create a probe directory without failing on Windows handle races."""

    def __init__(self, prefix):
        self.name = tempfile.mkdtemp(prefix=prefix)

    def __enter__(self):
        return self.name

    def __exit__(self, exception_type, exception, traceback):
        try:
            shutil.rmtree(self.name)
        except OSError:
            if os.name != 'nt' and exception_type is None:
                raise
        return False


def _temporary_directory(prefix):
    return _TemporaryDirectory(prefix)


def _check_rules(name, arguments, output, cwd, expected,
                 expected_diagnoses=(), helper_checks=False):
    """Check selected corrections and diagnoses against one real probe.

    The probe directory is still alive here, which matters for BSD ``cp`` and
    ``mv``: their wording is ambiguous unless the source operand really exists.
    This is deliberately opt-in metadata on a handful of safe probes rather
    than a claim that every command failure should have a correction.
    """
    from thebleep.api import suggest, why

    script = ' '.join([name] + list(arguments))
    previous = os.getcwd()
    try:
        os.chdir(str(cwd))
        try:
            if helper_checks:
                from thebleep.corrector import get_corrected_commands
                from thebleep.types import Command
                from thebleep.utils import tool_probes

                # Only explicitly selected probes may take this path. The
                # helper calls are still bounded by the rule utility, and the
                # failing command itself is never replayed.
                with tool_probes(True):
                    corrections = get_corrected_commands(
                        Command(script, output))
                result = {'suggestions': [
                    {'rule': getattr(item.rule, 'name', None)}
                    for item in corrections]}
            else:
                result = suggest(script, output)
        except Exception as error:                            # noqa: BLE001
            return {
                'expected_rules': list(expected),
                'matched_rules': [],
                'expected_diagnoses': list(expected_diagnoses),
                'matched_diagnoses': [],
                'passed': False,
                'error': str(error),
            }
    finally:
        os.chdir(previous)

    matched = [item['rule'] for item in result['suggestions']
               if item.get('rule')]
    check = {
        'expected_rules': list(expected),
        'matched_rules': matched,
        'passed': all(rule in matched for rule in expected),
    }
    if expected_diagnoses:
        try:
            diagnosis_result = why(
                script, output,
                platform_name='nt' if os.name == 'nt' else 'posix')
        except Exception as error:                            # noqa: BLE001
            check.update({
                'expected_diagnoses': list(expected_diagnoses),
                'matched_diagnoses': [],
                'passed': False,
                'error': str(error),
            })
        else:
            matched_diagnoses = [item['kind'] for item in
                                 diagnosis_result['diagnoses']]
            check.update({
                'expected_diagnoses': list(expected_diagnoses),
                'matched_diagnoses': matched_diagnoses,
                'passed': check['passed'] and all(
                    diagnosis in matched_diagnoses
                    for diagnosis in expected_diagnoses),
            })
    return check


def probe_commands(commands, check_rules=False):
    """Probe installed commands while isolating home/configuration files."""
    by_name = {item['name'].casefold(): item['path'] for item in commands}
    with _temporary_directory('thebleep-inventory-') as home:
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
                    platforms = specification.get('platforms')
                    expected_rules = specification.get('checks', ())
                    expected_diagnoses = specification.get('diagnoses', ())
                    helper_checks = specification.get('helper_checks', False)
                else:
                    arguments, files = specification, ()
                    platforms = None
                    expected_rules = ()
                    expected_diagnoses = ()
                    helper_checks = False
                current_platform = platform.system()
                if platforms and current_platform not in platforms:
                    continue
                with _temporary_directory('thebleep-probe-') as probe_directory:
                    for filename in files:
                        Path(probe_directory).joinpath(filename).touch()
                    probe_environment = environment.copy()
                    for variable in ('TMPDIR', 'TMP', 'TEMP'):
                        probe_environment[variable] = probe_directory
                    result = run_probe(
                        path, arguments, Path(probe_directory),
                        probe_environment)
                    if check_rules and (expected_rules or expected_diagnoses) \
                            and not result.get(
                            'timeout') and not result.get('output_truncated'):
                        result['rule_check'] = _check_rules(
                            name, arguments, result['output'],
                            probe_directory, expected_rules,
                            expected_diagnoses, helper_checks)
                    result.update({'command': name, 'path': path})
                    results.append(result)
    return results


def build_inventory(check_rules=False):
    commands = inventory_commands()
    probes = (probe_commands(commands, True) if check_rules
              else probe_commands(commands))
    return {
        'format': 1,
        'generated_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        'environment': {
            'runner_os': os.environ.get('RUNNER_OS'),
            # GitHub exposes ImageOS on hosted runners, but a container has
            # no such variable. The workflow supplies its matrix
            # label so an artifact remains self-describing.
            'runner_image': (os.environ.get('THEBLEEP_INVENTORY_IMAGE') or
                             os.environ.get('ImageOS')),
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'python': platform.python_version(),
            'shell': os.environ.get('SHELL') or os.environ.get('ComSpec'),
            'path_entries': _path_entries(),
        },
        'commands': commands,
        'probes': probes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='command-inventory.json',
                        help='JSON path to write (default: %(default)s)')
    parser.add_argument('--check-rules', action='store_true',
                        help='validate selected live probes against rules')
    args = parser.parse_args()
    destination = Path(args.output)
    inventory = build_inventory(args.check_rules)
    destination.write_text(json.dumps(inventory, indent=2, sort_keys=True) +
                           '\n', encoding='utf-8')
    print('recorded {} commands and {} probes in {}'.format(
        len(inventory['commands']), len(inventory['probes']), destination))
    failures = [probe for probe in inventory['probes']
                if probe.get('rule_check')
                and not probe['rule_check']['passed']]
    if failures:
        for probe in failures:
            check = probe['rule_check']
            expected = check.get('expected_rules', []) + check.get(
                'expected_diagnoses', [])
            print('{} {} no longer matches {}; see {}'.format(
                probe['command'], ' '.join(probe['arguments']),
                ', '.join(expected), destination),
                file=sys.stderr)
            if check.get('error'):
                print('  {}'.format(check['error']), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
