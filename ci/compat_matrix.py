#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Record what The Bleep answers to everyday slips on this machine.

    ci/compat_matrix.py record --label debian-13 --output rows/debian-13.json
    ci/compat_matrix.py render [--check]

`record` types each scenario's broken command into the shell, keeps what the
shell printed, hands command and output to the correction engine exactly as
`bleep` would, and writes down the first suggestion. Nothing suggested is ever
run: a scenario whose correction is `sudo cat /etc/shadow` records that text and
stops. The broken commands themselves are chosen to fail before they can do
anything.

The same script runs on a CI runner, in a container, in a BSD virtual machine
and on a laptop, and every row it writes has the same shape, so the table in
the README is built from rows recorded by whoever ran it, marked as such.

`render` turns the rows in docs/compat/rows into the README's compact table and
the full page under docs/compat, and `--check` fails when the README does not
already say what the rows say -- the test suite runs that.

"""

import argparse
import datetime
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ROWS = os.path.join(ROOT, 'docs', 'compat', 'rows')
PAGE = os.path.join(ROOT, 'docs', 'compat', 'README.md')
README = os.path.join(ROOT, 'README.md')
BEGIN = u'<!-- compat: written by ci/compat_matrix.py render -->'
END = u'<!-- end compat -->'
TIMEOUT = 10
LATENCY_RUNS = 5

POSIX_SHELLS = ('bash', 'zsh', 'fish', 'sh')
POWERSHELLS = ('pwsh', 'powershell')


# --------------------------------------------------------------------------
# The scenarios: what is typed, what the correction should be.
#
# Each is (id, column heading, function). The function gets the environment
# and returns None when the scenario does not apply here, or a dict with the
# broken command, a regular expression the first suggestion has to match, and
# optionally files to lay out first. `na` is a reason rather than a cross.
# --------------------------------------------------------------------------

def _git_typo(env):
    if not env.has('git'):
        return {'na': 'git is not installed'}
    return {'run': 'gti status', 'expect': r'^git status$'}


def _git_subcommand(env):
    if not env.has('git'):
        return {'na': 'git is not installed'}
    return {'run': 'git psuh', 'expect': r'^git push$', 'in': 'repo'}


def _ls_typo(env):
    if env.powershell:
        # `sl` is Set-Location in PowerShell, so nothing is wrong with it.
        return {'run': 'lss', 'expect': r'^(ls|Get-ChildItem)$'}
    if env.has('sl'):
        return {'na': 'the `sl` train is installed'}
    return {'run': 'sl -la', 'expect': r'^ls -la$'}


def _mkdir_parents(env):
    if env.powershell:
        return {'na': 'PowerShell mkdir creates parents by itself'}
    return {'run': 'mkdir a/b/c', 'expect': r'^mkdir -p a/b/c$'}


def _permission(env):
    if env.powershell:
        return {'na': 'no sudo on Windows'}
    if env.is_root:
        return {'na': 'recorded as root, nothing is denied'}
    if not (env.has('sudo') or env.has('doas')):
        return {'na': 'neither sudo nor doas is installed'}
    # Something root can read and we cannot: the password hashes where they
    # are, root's own directory where they are not (a Void container has no
    # /etc/shadow, macOS keeps its root files under /var).
    for target, verb in (('/etc/shadow', 'cat'), ('/etc/master.passwd', 'cat'),
                         ('/etc/sudoers', 'cat'), ('/root', 'ls'),
                         ('/var/root', 'ls')):
        if os.path.exists(target) and not os.access(target, os.R_OK):
            break
    else:
        return {'na': 'nothing here is denied to this user'}
    return {'run': verb + ' ' + target,
            'expect': r'^(sudo|doas) ' + verb + ' ' + re.escape(target) + '$'}


def _chmod(env):
    if env.powershell:
        return {'na': 'no execute bit on Windows'}
    return {'run': './script.sh',
            'expect': r'^chmod \+x script\.sh && \./script\.sh$',
            'files': {'script.sh': ('#!/bin/sh\necho hi\n', False)}}


def _cd_typo(env):
    return {'run': 'cd Documnets', 'expect': r'^cd Documents$',
            'dirs': ['Documents']}


def _rm_dir(env):
    if env.powershell:
        return {'na': 'PowerShell asks about a directory instead'}
    return {'run': 'rm emptydir', 'expect': r'^rm -r(f)? emptydir$',
            'dirs': ['emptydir']}


def _not_on_path(env):
    if env.powershell:
        # A tool dropped where installers put things, off PATH.
        return {'run': 'hellotool',
                'expect': r'hellotool',
                'files': {'.local/bin/hellotool.cmd':
                          ('@echo off\r\necho hi\r\n', True)},
                'home': True}
    return {'run': 'hellotool',
            'expect': r'(\.local/bin/hellotool|PATH=.*hellotool)',
            'files': {'.local/bin/hellotool': ('#!/bin/sh\necho hi\n', True)},
            'home': True}


def _unknown_flag(env):
    if not env.has('git'):
        return {'na': 'git is not installed'}
    return {'run': 'git status --shrot', 'expect': r'^git status --short$',
            'in': 'repo'}


def _package_manager(env):
    managers = [
        ('apt', 'apt isntall vim', r'^(sudo )?apt install vim$'),
        ('dnf', 'dnf isntall vim', r'^(sudo )?dnf install vim$'),
        ('yum', 'yum isntall vim', r'^(sudo )?yum install vim$'),
        ('zypper', 'zypper isntall vim', r'^(sudo )?zypper install vim$'),
        ('pacman', 'pacman -s vim', r'^pacman -S vim$'),
        ('apk', 'apk isntall vim', r'^(sudo )?apk add vim$'),
        ('pkg', 'pkg isntall vim', r'^(sudo |doas )?pkg install vim$'),
        # pkg_add takes package names too, and a wrong one goes to the
        # network; the slip is in the program's name.
        ('pkg_add', 'pkg_ad vim', r'^pkg_add vim$'),
        # xbps-install takes package names, so a mistyped verb is a missing
        # package rather than a slip; the slip Void users make is in the
        # program's own name.
        ('xbps-install', 'xbps-instal -S vim', r'^xbps-install -S vim$'),
        ('brew', 'brew isntall wget', r'^brew install wget$'),
        ('winget', 'winget isntall vim', r'^winget install vim$'),
        ('choco', 'choco isntall vim', r'^choco install vim$'),
        ('scoop', 'scoop isntall vim', r'^scoop install vim$'),
    ]
    for name, run, expect in managers:
        if env.has(name):
            return {'run': run, 'expect': expect, 'tool': name}
    return {'na': 'no package manager found'}


def _docker(env):
    if not env.has('docker'):
        return {'na': 'docker is not installed'}
    return {'run': 'docker pss', 'expect': r'^docker ps$'}


def _npm(env):
    if not env.has('npm'):
        return {'na': 'npm is not installed'}
    return {'run': 'npm run bulid', 'expect': r'^npm run build$',
            'files': {'package.json': (
                '{"name": "x", "version": "1.0.0", '
                '"scripts": {"build": "echo built"}}\n', False)}}


def _cargo(env):
    if not env.has('cargo'):
        return {'na': 'cargo is not installed'}
    if not env.works(['cargo', '--version']):
        # GitHub's runners ship rustup's proxy with no toolchain behind it;
        # what that prints is about rustup, not about the slip.
        return {'na': 'cargo has no toolchain here'}
    return {'run': 'cargo biuld', 'expect': r'^cargo build$'}


def _cd_parent(env):
    if env.powershell:
        return {'na': 'PowerShell accepts `cd..` as it is'}
    return {'run': 'cd..', 'expect': r'^cd \.\.$'}


SCENARIOS = [
    ('git_typo', u'`gti status`', _git_typo),
    ('git_subcommand', u'`git psuh`', _git_subcommand),
    ('ls_typo', u'`sl -la`', _ls_typo),
    ('unknown_flag', u'`git status --shrot`', _unknown_flag),
    ('package_manager', u'`apt isntall`, `dnf`, `apk`…', _package_manager),
    ('permission', u'permission denied', _permission),
    ('mkdir_parents', u'`mkdir a/b/c`', _mkdir_parents),
    ('chmod', u'`./script.sh` without +x', _chmod),
    ('cd_typo', u'`cd Documnets`', _cd_typo),
    ('rm_dir', u'`rm` a directory', _rm_dir),
    ('not_on_path', u'installed, not on PATH', _not_on_path),
    ('cd_parent', u'`cd..`', _cd_parent),
    ('docker', u'`docker pss`', _docker),
    ('npm', u'`npm run bulid`', _npm),
    ('cargo', u'`cargo biuld`', _cargo),
]


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------

class Environment(object):
    def __init__(self, shell):
        self.shell = shell
        self.powershell = shell in POWERSHELLS
        self.is_root = hasattr(os, 'geteuid') and os.geteuid() == 0
        self._found = {}

    def has(self, name):
        if name not in self._found:
            self._found[name] = shutil.which(name) is not None
        return self._found[name]

    def works(self, command):
        """Whether `command` runs and exits 0, for tools that are on PATH
        but not usable."""
        try:
            return subprocess.run(command, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                  timeout=TIMEOUT).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def _default_shell():
    if os.name == 'nt':
        return 'pwsh' if shutil.which('pwsh') else 'powershell'
    for name in POSIX_SHELLS:
        if shutil.which(name):
            return name
    return 'sh'


def _shell_command(shell, script):
    if shell in POWERSHELLS:
        return [shell, '-NoProfile', '-NonInteractive', '-Command',
                '& { ' + script + ' } 2>&1 | Out-String -Width 200']
    if shell == 'fish':
        return [shell, '--no-config', '-c', script + ' 2>&1']
    return [shell, '-c', script + ' 2>&1']


def _run_broken(shell, script, cwd, environment):
    try:
        completed = subprocess.run(
            _shell_command(shell, script), cwd=cwd, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, u'could not run the shell: {}'.format(error)
    output = completed.stdout.decode('utf-8', 'replace')
    return completed.returncode, output


def _lay_out(scenario, cwd, home):
    for name in scenario.get('dirs', ()):
        os.makedirs(os.path.join(cwd, name), exist_ok=True)
    for name, (text, executable) in scenario.get('files', {}).items():
        base = home if scenario.get('home') else cwd
        path = os.path.join(base, *name.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, 'w', encoding='utf-8', newline='') as handle:
            handle.write(text)
        if executable and os.name != 'nt':
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    if scenario.get('in') == 'repo':
        repo = os.path.join(cwd, 'repo')
        subprocess.run(['git', 'init', '-q', repo], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return repo
    return cwd


def _suggest(script, output, cwd):
    """The engine's answer, from the scenario's directory, the way `bleep`
    at the prompt gets it: the shell in TB_SHELL, the output already
    captured, and rules allowed to ask an installed tool for its help text.
    The structured API keeps those probes off, which is right for an agent
    and wrong for a table about what the prompt does."""
    from thebleep.corrector import get_corrected_commands
    from thebleep.types import Command
    from thebleep.utils import tool_probes

    previous = os.getcwd()
    os.chdir(cwd)
    try:
        with tool_probes(True):
            corrected = list(get_corrected_commands(Command(script, output)))
    finally:
        os.chdir(previous)
    return [(item.script, getattr(getattr(item, 'rule', None), 'name', None))
            for item in corrected]


def _tidy(text, home, cwd):
    """The scratch directories as a reader would see their own."""
    return text.replace(cwd, '.').replace(home, '~')


def _record_one(scenario, env, workspace, home, environment):
    if 'na' in scenario:
        return {'status': 'na', 'reason': scenario['na']}
    cwd = tempfile.mkdtemp(prefix='scenario-', dir=workspace)
    cwd = _lay_out(scenario, cwd, home)
    status, output = _run_broken(env.shell, scenario['run'], cwd, environment)
    if status is None:
        return {'status': 'error', 'ran': scenario['run'], 'reason': output}
    if status == 0 and scenario.get('skip_if_succeeds'):
        return {'status': 'na', 'ran': scenario['run'],
                'reason': 'the command succeeded here'}
    try:
        answer = _suggest(scenario['run'], output, cwd)
    except Exception as error:                                 # noqa: BLE001
        return {'status': 'error', 'ran': scenario['run'],
                'output': output[-1500:], 'reason': repr(error)}
    suggestions = [_tidy(script, home, cwd) for script, _ in answer]
    record = {
        'ran': scenario['run'],
        'exit_status': status,
        'output': _tidy(output.strip()[-1500:], home, cwd),
        'suggestions': suggestions[:3],
        'rule': answer[0][1] if answer else None,
    }
    if scenario.get('tool'):
        record['tool'] = scenario['tool']
    if not suggestions:
        record['status'] = 'miss'
    elif re.search(scenario['expect'], suggestions[0]):
        record['status'] = 'ok'
        record['correction'] = suggestions[0]
    else:
        record['status'] = 'other'
        record['correction'] = suggestions[0]
    return record


def _latency(shell, environment):
    """Milliseconds for a command-only correction, process start included:
    what the keystroke path pays. The median of a few runs."""
    command = [sys.executable, '-m', 'thebleep', '--inline', 'gti status']
    samples = []
    for _ in range(LATENCY_RUNS):
        started = time.time()
        try:
            completed = subprocess.run(command, env=environment,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL,
                                       timeout=TIMEOUT)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.stdout.strip() != b'git status':
            return None
        samples.append((time.time() - started) * 1000)
    samples.sort()
    return int(round(samples[len(samples) // 2]))


def _describe_system():
    system = platform.system()
    if system == 'Linux':
        try:
            with io.open('/etc/os-release', encoding='utf-8') as handle:
                for line in handle:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=', 1)[1].strip().strip('"')
        except OSError:
            pass
        return 'Linux ' + platform.release()
    if system == 'Darwin':
        return 'macOS ' + platform.mac_ver()[0]
    if system == 'Windows':
        return 'Windows ' + platform.version()
    return '{} {}'.format(system, platform.release())


def _shell_version(shell):
    probes = {
        'bash': ['bash', '-c', 'echo $BASH_VERSION'],
        'zsh': ['zsh', '-c', 'echo $ZSH_VERSION'],
        'fish': ['fish', '--version'],
        'sh': ['sh', '-c', 'echo sh'],
        'pwsh': ['pwsh', '-NoProfile', '-Command',
                 '$PSVersionTable.PSVersion.ToString()'],
        'powershell': ['powershell', '-NoProfile', '-Command',
                       '$PSVersionTable.PSVersion.ToString()'],
    }
    try:
        text = subprocess.run(probes[shell], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=TIMEOUT
                              ).stdout.decode('utf-8', 'replace').strip()
    except (KeyError, OSError, subprocess.TimeoutExpired):
        text = ''
    text = text.replace('fish, version ', '')
    return u'{} {}'.format(shell, text).strip()


def _thebleep_version():
    try:
        from importlib.metadata import version
        return version('thebleep')
    except Exception:                                          # noqa: BLE001
        return None


def record(args):
    shell = args.shell or _default_shell()
    if not shutil.which(shell):
        sys.exit('compat_matrix.py: no {} on this machine'.format(shell))
    workspace = tempfile.mkdtemp(prefix='thebleep-compat-')
    home = os.path.join(workspace, 'home')
    os.makedirs(home)
    environment = dict(os.environ)
    # A home of its own: nothing this writes lands in the real one, and the
    # "installed, off PATH" scenario needs a ~/.local/bin it can fill.
    environment['HOME'] = home
    if os.name == 'nt':
        environment['USERPROFILE'] = home
    environment['XDG_CONFIG_HOME'] = os.path.join(home, '.config')
    environment['XDG_CACHE_HOME'] = os.path.join(home, '.cache')
    environment['TB_SHELL'] = 'powershell' if shell in POWERSHELLS else shell
    environment.pop('TB_SHELL_ALIASES', None)
    environment['GIT_CONFIG_GLOBAL'] = os.devnull
    environment['GIT_AUTHOR_NAME'] = environment['GIT_COMMITTER_NAME'] = 'x'
    environment['GIT_AUTHOR_EMAIL'] = environment['GIT_COMMITTER_EMAIL'] = \
        'x@x'
    os.environ.update(environment)

    env = Environment(shell)
    row = {
        'schema': 1,
        'label': args.label,
        'system': _describe_system(),
        'machine': platform.machine(),
        'shell': _shell_version(shell),
        'python': platform.python_version(),
        'thebleep': _thebleep_version(),
        'recorded_at': datetime.datetime.now(datetime.timezone.utc)
        .strftime('%Y-%m-%d'),
        'recorded_by': args.recorded_by,
        'source': args.source,
        'cells': {},
    }
    try:
        for identifier, _, scenario_of in SCENARIOS:
            scenario = scenario_of(env)
            cell = _record_one(scenario, env, workspace, home, environment)
            row['cells'][identifier] = cell
            mark = {'ok': u'ok  ', 'na': u'n/a ', 'miss': u'MISS',
                    'other': u'OTHER', 'error': u'ERR '}[cell['status']]
            detail = cell.get('correction') or cell.get('reason') or ''
            print(u'{} {:<16} {}'.format(mark, identifier, detail))
        row['latency_ms'] = _latency(shell, environment)
        print(u'latency: {} ms'.format(row['latency_ms']))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    output = args.output or os.path.join(ROWS, args.label + '.json')
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with io.open(output, 'w', encoding='utf-8') as handle:
        json.dump(row, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write(u'\n')
    print(u'wrote {}'.format(output))
    problems = [identifier for identifier, cell in row['cells'].items()
                if cell['status'] in ('miss', 'other', 'error')]
    if problems and args.strict:
        sys.exit('compat_matrix.py: not corrected here: ' +
                 ', '.join(sorted(problems)))
    return 0


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

MARKS = {'ok': u'✓', 'na': u'—', 'miss': u'✗', 'other': u'✗', 'error': u'✗'}


def load_rows(directory=ROWS):
    rows = []
    if not os.path.isdir(directory):
        return rows
    for name in sorted(os.listdir(directory)):
        if name.endswith('.json'):
            with io.open(os.path.join(directory, name),
                         encoding='utf-8') as handle:
                rows.append(json.load(handle))
    rows.sort(key=lambda row: (_family(row['system']), row['label']))
    return rows


def _family(system):
    lowered = system.lower()
    for index, word in enumerate(('debian', 'ubuntu', 'fedora', 'alma',
                                  'rocky', 'centos', 'arch', 'suse', 'alpine',
                                  'void', 'gentoo', 'linux', 'freebsd',
                                  'openbsd', 'netbsd', 'macos', 'windows')):
        if word in lowered:
            return index
    return 99


def _row_name(row):
    # The distribution's own name, minus the codename in brackets that
    # AlmaLinux and Ubuntu add, plus whatever tells two rows apart: the shell
    # when it is not the platform's usual one, WSL, and a row recorded by a
    # person rather than by the workflow.
    name = re.sub(r'\s*\([^)]*\)', '', row['system']).replace(
        'GNU/Linux ', '')
    shell = row['shell'].split()[0] if row['shell'] else ''
    if 'wsl' in row['label']:
        name += ' on WSL'
    usual = 'zsh' if 'macos' in row['system'].lower() else 'bash'
    if shell and shell != usual:
        name += u' ({})'.format(shell)
    if row.get('recorded_by') == 'hand':
        name += u' · by hand'
    return name


def compact_table(rows):
    """The README's table: a mark per cell, the correction on hover through
    the title of a link would be nice, but plain Markdown has no hover, so
    the corrections themselves are on the full page."""
    columns = [heading for _, heading, _ in SCENARIOS]
    lines = [u'| | ' + u' | '.join(columns) + u' | ms |',
             u'|---|' + u'|'.join(':-:' for _ in columns) + u'|--:|']
    for row in rows:
        marks = [MARKS[row['cells'][identifier]['status']]
                 if identifier in row['cells'] else u'—'
                 for identifier, _, _ in SCENARIOS]
        latency = row.get('latency_ms')
        lines.append(u'| **{}** | {} | {} |'.format(
            _row_name(row), u' | '.join(marks),
            latency if latency is not None else u''))
    return u'\n'.join(lines)


def _legend(rows):
    count = len(rows)
    corrected = sum(1 for row in rows for cell in row['cells'].values()
                    if cell['status'] == 'ok')
    applicable = sum(1 for row in rows for cell in row['cells'].values()
                     if cell['status'] != 'na')
    return (u'{} platforms, {} of {} applicable slips corrected. ✓ the first '
            u'suggestion was the right command; — the slip cannot happen '
            u'there; ✗ it was not corrected. *ms* is the wall time of a '
            u'command-only correction, Python start included, median of '
            u'{} runs. Every cell was recorded by '
            u'[ci/compat_matrix.py](ci/compat_matrix.py) typing the slip '
            u'into that platform\'s shell and reading the answer, never by '
            u'hand; the corrections themselves are on the [full page]'
            u'(docs/compat/README.md).').format(
                count, corrected, applicable, LATENCY_RUNS)


def block(rows):
    return u'\n'.join([BEGIN, compact_table(rows), u'', _legend(rows), END])


def _cell_text(cell):
    status = cell['status']
    if status == 'ok':
        return u'✓ `{}`'.format(cell['correction'])
    if status == 'na':
        return u'— {}'.format(cell['reason'])
    if status == 'miss':
        return u'✗ nothing suggested'
    if status == 'other':
        return u'✗ suggested `{}`'.format(cell['correction'])
    return u'✗ error: {}'.format(cell.get('reason', ''))


def page(rows):
    lines = [
        u'# Where it works',
        u'',
        u'Each row is one machine, one shell. The broken command in each',
        u'column was typed into that shell by `ci/compat_matrix.py`, what the',
        u'shell printed was handed to the correction engine, and the first',
        u'suggestion is what the cell says. Nothing suggested was run.',
        u'',
        u'Rows marked *ci* were recorded by the weekly',
        u'[compatibility workflow](../../.github/workflows/compat-matrix.yml)',
        u'on a fresh runner, container or virtual machine; rows marked *hand*',
        u'by a person running the same script on a machine CI cannot reach.',
        u'',
    ]
    for row in rows:
        lines.append(u'## {}'.format(_row_name(row)))
        lines.append(u'')
        lines.append(u'`{}` · {} · Python {} · The Bleep {} · recorded {} '
                     u'by {} from {}'.format(
                         row['label'], row['shell'], row['python'],
                         row.get('thebleep') or '?', row['recorded_at'],
                         row['recorded_by'], row.get('source', '?')))
        if row.get('latency_ms') is not None:
            lines.append(u'')
            lines.append(u'Command-only correction in {} ms, median of {} '
                         u'runs, Python start included.'.format(
                             row['latency_ms'], LATENCY_RUNS))
        lines.append(u'')
        lines.append(u'| slip | typed | answer |')
        lines.append(u'|---|---|---|')
        for identifier, heading, _ in SCENARIOS:
            cell = row['cells'].get(identifier)
            if cell is None:
                continue
            typed = u'`{}`'.format(cell['ran']) if cell.get('ran') else u''
            lines.append(u'| {} | {} | {} |'.format(
                heading, typed, _cell_text(cell)))
        lines.append(u'')
    return u'\n'.join(lines)


def _read(path):
    with io.open(path, encoding='utf-8') as handle:
        return handle.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def readme_with_block(text, rows):
    if BEGIN not in text or END not in text:
        sys.exit('compat_matrix.py: README.md has no compat block; put\n'
                 '{}\n{}\nwhere the table should go.'.format(BEGIN, END))
    start = text.index(BEGIN)
    finish = text.index(END) + len(END)
    return text[:start] + block(rows) + text[finish:]


def render(args):
    rows = load_rows(args.rows)
    if not rows:
        sys.exit('compat_matrix.py: no rows in {}'.format(args.rows))
    text = _read(README)
    wanted = readme_with_block(text, rows)
    wanted_page = page(rows)
    if args.check:
        current_page = _read(PAGE) if os.path.exists(PAGE) else u''
        if text != wanted or current_page != wanted_page:
            sys.exit('compat_matrix.py: README.md or docs/compat/README.md '
                     'do not say what docs/compat/rows say; run '
                     '`python ci/compat_matrix.py render`.')
        print('README.md and docs/compat/README.md say what the rows say.')
        return 0
    _write(README, wanted)
    _write(PAGE, wanted_page)
    print('wrote the compat block in README.md and docs/compat/README.md '
          '({} rows)'.format(len(rows)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0])
    commands = parser.add_subparsers(dest='command')
    commands.required = True

    recording = commands.add_parser('record', help='record this machine')
    recording.add_argument('--label', required=True,
                           help='row name, e.g. debian-13 or macos-15-zsh')
    recording.add_argument('--shell', help='shell to type into '
                           '(default: the first of bash, zsh, fish, sh; '
                           'pwsh or powershell on Windows)')
    recording.add_argument('--output', help='where to write the row '
                           '(default: docs/compat/rows/<label>.json)')
    recording.add_argument('--recorded-by', default='hand',
                           choices=('ci', 'hand'))
    recording.add_argument('--source', default='checkout',
                           help='what was installed: checkout, pypi, ...')
    recording.add_argument('--strict', action='store_true',
                           help='exit non-zero when a slip was not corrected')
    recording.set_defaults(run=record)

    rendering = commands.add_parser('render', help='write the tables')
    rendering.add_argument('--rows', default=ROWS)
    rendering.add_argument('--check', action='store_true',
                           help='write nothing; fail if the README is stale')
    rendering.set_defaults(run=render)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == '__main__':
    sys.exit(main())
