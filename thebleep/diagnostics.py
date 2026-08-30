# -*- encoding: utf-8 -*-

"""Deterministic explanations for failures that are not command typos.

The correction rules answer "what should I have typed instead?". Some failures
are already valid commands, so a better answer is a small, factual diagnosis.
This module deliberately only reads the supplied output: it never probes the
machine, reruns the command, or turns an extracted value into an executable
action.
"""

import ast
import os
import re
import shlex


_PORT_IN_OUTPUT = re.compile(
    r'(?:\bport(?:\s+|=)|:)([0-9]{1,5})\b', re.IGNORECASE)
_PORT_IN_COMMAND = re.compile(
    r'(?:--?port(?:=|\s+)|\s-p(?:\s+|=))([0-9]{1,5})\b', re.IGNORECASE)
_MODULE = re.compile(
    r"(?:ModuleNotFoundError: )?No module named ['\"]([^'\"]+)['\"]")
_DNS_HOST = re.compile(r'could not resolve host:\s*([^\s]+)', re.IGNORECASE)
_DNS_HOSTNAME = re.compile(
    r'could not resolve hostname\s+([^:\s]+)', re.IGNORECASE)
_DNS_BAD_ADDRESS = re.compile(
    r"bad address ['\"]([^'\"\r\n]+)['\"]", re.IGNORECASE)
_READ_ONLY_FS = re.compile(r'read[- ]only file system', re.IGNORECASE)
_DOCKER_DAEMON = re.compile(
    r'(?:cannot connect to the docker daemon|'
    r'failed to connect to the docker api)', re.IGNORECASE)
_SSH_HOST_WARNING = re.compile(
    r'WARNING: (?:REMOTE HOST IDENTIFICATION HAS CHANGED|'
    r'POSSIBLE DNS SPOOFING DETECTED)!', re.IGNORECASE)
_SSH_HOST = re.compile(
    r"host key for ['\"]?([^'\"\s]+)['\"]? (?:has changed|differs)",
    re.IGNORECASE)
_MISSING_INTERFACE = re.compile(
    r'(?:interface\s+(?P<name>[^\s:]+)\s+does not exist|'
    r'(?P<linux_name>[^\s:]+):\s+error fetching interface information:'
    r'\s+device not found)', re.IGNORECASE)
_PYTHON_PATH_ERROR = re.compile(
    r'(?P<kind>FileNotFoundError|PermissionError): '
    r'\[(?:Errno|WinError) \d+\] '
    r'(?P<message>[^:\r\n]+): '
    r'(?P<quote>[\'\"])(?P<path>(?:\\.|(?!(?P=quote)).)*)(?P=quote)')


_POSIX_PERMISSION_PATH = re.compile(
    r'''(?im)^[^:\r\n]+:\s+(?:cannot [^'"\r\n]+ )?
        (?P<quote>['"]?)(?P<path>[^'"\r\n]+?)(?P=quote):
        \s*permission[ ]denied''', re.VERBOSE)
_POSIX_MISSING_PATH = re.compile(
    r'''(?im)^[^:\r\n]+:\s+(?:(?:cannot|can't)[^'"\r\n]+[ ])?
        (?P<quote>['"]?)(?P<path>[^'"\r\n]+?)(?P=quote):
        \s*no[ ]such[ ]file[ ]or[ ]directory''', re.VERBOSE)
_POSIX_EXISTING_PATH = re.compile(
    r'''(?im)^[^:\r\n]+:\s+(?:failed[ ]to[ ]create[ ]symbolic[ ]link[ ])?
        (?P<quote>['"]?)(?P<path>[^'"\r\n]+?)(?P=quote):
        \s*file[ ]exists''', re.VERBOSE)
_POSIX_MISSING_MOVE = re.compile(
    r'''(?im)^[^:\r\n]+:\s+rename\s+(?P<source>.+?)\s+to\s+
        (?P<destination>[^:\r\n]+):\s*no[ ]such[ ]file[ ]or[ ]directory''',
    re.VERBOSE)


def _port(script, output):
    """Returns a valid port explicitly present in the supplied context."""
    for source, pattern in ((output, _PORT_IN_OUTPUT),
                            (script, _PORT_IN_COMMAND)):
        for value in pattern.findall(source or ''):
            if 0 < int(value) < 65536:
                return value
    return None


def _step(command, reason):
    return {'command': command, 'reason': reason, 'risk': 'read-only'}


def _shell_command(posix, windows, platform_name):
    """Return a read-only follow-up for the target platform."""
    return windows if platform_name == 'nt' else posix


def _quote(value, platform_name):
    """Quote a value for a displayed follow-up command."""
    if platform_name != 'nt':
        return shlex.quote(value)
    return "'{}'".format(value.replace("'", "''"))


def _python_error_path(output, kind):
    match = _PYTHON_PATH_ERROR.search(output)
    if not match or match.group('kind') != kind:
        return None

    literal = '{}{}{}'.format(
        match.group('quote'), match.group('path'), match.group('quote'))
    try:
        path = ast.literal_eval(literal)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(path, str) or not path:
        return None
    return match, path


def _posix_path(output, pattern):
    match = pattern.search(output)
    if not match:
        return None

    quote = match.group('quote')
    literal = '{}{}{}'.format(quote, match.group('path'), quote)
    try:
        path = ast.literal_eval(literal) if quote else match.group('path')
    except (SyntaxError, ValueError):
        return None
    if not isinstance(path, str) or not path:
        return None
    return match, path


def _posix_permission_path(output):
    return _posix_path(output, _POSIX_PERMISSION_PATH)


def _posix_missing_path(output):
    move = _POSIX_MISSING_MOVE.search(output)
    if move:
        paths = []
        for name in ('source', 'destination'):
            value = move.group(name).strip()
            if len(value) >= 2 and value[0] == value[-1] \
                    and value[0] in "'\"":
                literal = '{}{}{}'.format(value[0], value[1:-1], value[0])
                try:
                    value = ast.literal_eval(literal)
                except (SyntaxError, ValueError):
                    return None
            if not value:
                return None
            paths.append(value)
        return move, paths
    return _posix_path(output, _POSIX_MISSING_PATH)


def _posix_existing_path(output):
    return _posix_path(output, _POSIX_EXISTING_PATH)


def _path_inspection(path, platform_name, permission=False):
    if platform_name == 'nt':
        command = 'Get-Acl' if permission else 'Get-Item'
        return '{} -LiteralPath {}'.format(
            command, _quote(path, platform_name))

    # BSD ls has no `--`; make a relative option-looking path explicit.
    displayed_path = './{}'.format(path) if path.startswith('-') else path
    return 'ls -ld {}'.format(_quote(displayed_path, platform_name))


def _address_in_use(script, output, platform_name):
    if not re.search(r'address already in use', output, re.IGNORECASE):
        return None

    port = _port(script, output)
    evidence = ['address already in use']
    next_steps = []
    if port:
        evidence.append('port {}'.format(port))
        next_steps.append(_step(
            _shell_command(
                'lsof -nP -iTCP:{} -sTCP:LISTEN'.format(port),
                'netstat -ano -p tcp | findstr ":{}"'.format(port),
                platform_name),
            'find the process listening on this port'))
    return {
        'kind': 'address_in_use',
        'summary': ('Port {} is already in use.'.format(port)
                    if port else 'A network address is already in use.'),
        'evidence': evidence,
        'next_steps': next_steps,
    }


def _permission_denied(script, output, platform_name):
    if not re.search(r'(?:permission denied|access is denied)', output,
                     re.IGNORECASE):
        return None
    match = re.search(r'permission denied|access is denied', output,
                      re.IGNORECASE)
    path_error = (_python_error_path(output, 'PermissionError')
                  if 'PermissionError' in output else None)
    if not path_error and platform_name != 'nt':
        path_error = _posix_permission_path(output)
    next_steps = []
    if path_error:
        next_steps.append(_step(
            _path_inspection(path_error[1], platform_name, permission=True),
            'inspect permissions on the denied path'))
    return {
        'kind': 'permission_denied',
        'summary': 'The operating system denied the operation.',
        'evidence': [match.group(0).lower()],
        'next_steps': next_steps,
    }


def _certificate_expired(script, output, platform_name):
    if not re.search(r'certificate has expired', output, re.IGNORECASE):
        return None
    match = re.search(r'certificate has expired', output, re.IGNORECASE)
    return {
        'kind': 'certificate_expired',
        'summary': 'The peer certificate could not be trusted because it is '
                   'expired.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            _shell_command('date -u', '[DateTime]::UtcNow', platform_name),
            'check the local clock')],
    }


def _disk_full(script, output, platform_name):
    if not re.search(r'no space left on device|disk full', output,
                     re.IGNORECASE):
        return None
    match = re.search(r'no space left on device|disk full', output,
                      re.IGNORECASE)
    return {
        'kind': 'disk_full',
        'summary': 'The filesystem is out of space.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            _shell_command(
                'df -h',
                'Get-PSDrive -PSProvider FileSystem',
                platform_name),
            'inspect filesystem capacity')],
    }


def _connection_refused(script, output, platform_name):
    if not re.search(r'connection refused', output, re.IGNORECASE):
        return None
    match = re.search(r'connection refused', output, re.IGNORECASE)
    port = _port(script, output)
    evidence = [match.group(0).lower()]
    next_steps = []
    if port:
        evidence.append('port {}'.format(port))
        next_steps.append(_step(
            _shell_command(
                'lsof -nP -iTCP:{} -sTCP:LISTEN'.format(port),
                'netstat -ano -p tcp | findstr ":{}"'.format(port),
                platform_name),
            'check whether anything is listening on this port'))
    return {
        'kind': 'connection_refused',
        'summary': ('The target refused the connection on port {}.'.format(
            port) if port else 'The target refused the connection.'),
        'evidence': evidence,
        'next_steps': next_steps,
    }


def _docker_daemon(script, output, platform_name):
    match = _DOCKER_DAEMON.search(output)
    if not match:
        return None
    return {
        'kind': 'docker_daemon_unavailable',
        'summary': 'Docker could not reach its daemon.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            'docker info',
            'check whether the Docker daemon is reachable')],
    }


def _ssh_host_key(script, output, platform_name):
    warning = _SSH_HOST_WARNING.search(output)
    if not warning:
        return None

    host = _SSH_HOST.search(output)
    evidence = [warning.group(0).lower()]
    next_steps = []
    if host:
        name = host.group(1)
        evidence.append('host {}'.format(name))
        next_steps.append(_step(
            'ssh-keygen -F {}'.format(_quote(name, platform_name)),
            'inspect the stored key before changing it'))

    return {
        'kind': 'ssh_host_key_changed',
        'summary': 'SSH rejected the host key; verify the server identity.',
        'evidence': evidence,
        'next_steps': next_steps,
    }


def _missing_module(script, output, platform_name):
    match = _MODULE.search(output)
    if not match:
        return None
    module = match.group(1)
    return {
        'kind': 'missing_python_module',
        'summary': 'Python could not import module {!r}.'.format(module),
        'evidence': ["No module named '{}'".format(module)],
        'next_steps': [_step(
            '{} -m pip show {}'.format(
                _shell_command('python', 'python', platform_name),
                _quote(module, platform_name)),
            'check whether a distribution with this name is installed')],
    }


def _missing_python_path(script, output, platform_name):
    path_error = _python_error_path(output, 'FileNotFoundError')
    if not path_error and platform_name != 'nt':
        path_error = _posix_missing_path(output)
    if not path_error:
        return None
    match, paths = path_error
    if not isinstance(paths, (list, tuple)):
        paths = [paths]
    return {
        'kind': 'missing_path',
        'summary': ('Python could not find the requested path.'
                    if match.groupdict().get('message')
                    else 'The requested path does not exist.'),
        'evidence': [match.group('message').strip().lower()
                     if match.groupdict().get('message')
                     else 'no such file or directory'],
        'next_steps': [_step(
            _path_inspection(path, platform_name),
            'check whether the requested path exists') for path in paths],
    }


def _existing_path(script, output, platform_name):
    path_error = _posix_existing_path(output)
    if not path_error:
        return None
    match, path = path_error
    return {
        'kind': 'path_already_exists',
        'summary': 'The path {!r} already exists.'.format(path),
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            _path_inspection(path, platform_name),
            'inspect the existing path')],
    }


def _dns_failure(script, output, platform_name):
    match = _DNS_HOST.search(output)
    if match is None:
        match = _DNS_HOSTNAME.search(output)
    if match is None:
        match = _DNS_BAD_ADDRESS.search(output)
    if not match:
        return None

    host = match.group(1).rstrip('.,;')
    if not host:
        return None
    evidence = match.group(0).lower()
    return {
        'kind': 'dns_failure',
        'summary': 'The hostname could not be resolved.',
        'evidence': [evidence],
        'next_steps': [_step(
            _shell_command(
                'getent hosts {}'.format(_quote(host, platform_name)),
                'Resolve-DnsName {}'.format(_quote(host, platform_name)),
                platform_name),
            'check whether DNS can resolve the hostname')],
    }


def _read_only_filesystem(script, output, platform_name):
    match = _READ_ONLY_FS.search(output)
    if not match:
        return None
    return {
        'kind': 'read_only_filesystem',
        'summary': 'The filesystem rejected the write because it is mounted '
                   'read-only.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            _shell_command('mount', 'Get-Volume', platform_name),
            'inspect filesystem mount or volume state')],
    }


def _dubious_ownership(script, output, platform_name):
    if not re.search(r'detected dubious ownership', output, re.IGNORECASE):
        return None
    match = re.search(r'detected dubious ownership', output, re.IGNORECASE)
    return {
        'kind': 'git_dubious_ownership',
        'summary': 'Git refused to trust this repository ownership.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            'git config --show-origin --get-all safe.directory',
            'inspect the configured trusted repositories')],
    }


def _git_not_repository(script, output, platform_name):
    if not re.search(r'not a git repository', output, re.IGNORECASE):
        return None
    match = re.search(r'not a git repository', output, re.IGNORECASE)
    return {
        'kind': 'git_not_repository',
        'summary': 'Git could not find a repository here or in a parent '
                   'directory.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            _shell_command('pwd', 'Get-Location', platform_name),
            'check the directory where the command is running')],
    }


def _git_conflict(script, output, platform_name):
    match = re.search(
        r'(?im)^(?:conflict \([^\r\n]+|automatic merge failed; '
        r'fix conflicts)', output)
    if not match:
        return None
    return {
        'kind': 'git_conflict',
        'summary': 'Git stopped because changes conflict.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            'git status --short',
            'list the files that need attention')],
    }


def _missing_interface(script, output, platform_name):
    if platform_name != 'posix':
        return None
    match = _MISSING_INTERFACE.search(output)
    if not match:
        return None
    name = match.group('name') or match.group('linux_name')
    if match.group('linux_name'):
        try:
            parts = shlex.split(script, posix=platform_name != 'nt')
        except ValueError:
            parts = []
        for index, part in enumerate(parts):
            if part.rsplit('/', 1)[-1] != 'ifconfig':
                continue
            for candidate in parts[index + 1:]:
                if not candidate.startswith('-') and candidate.startswith(name):
                    name = candidate
                    break
            break
    return {
        'kind': 'missing_network_interface',
        'summary': 'Network interface {!r} does not exist.'.format(
            name),
        'evidence': [match.group(0).lower()],
        'next_steps': [_step(
            'ifconfig -a',
            'list the available network interfaces')],
    }


_DETECTORS = (_address_in_use, _permission_denied, _certificate_expired,
              _disk_full, _connection_refused, _missing_module,
              _missing_python_path, _existing_path, _git_not_repository,
              _git_conflict,
              _dubious_ownership, _dns_failure, _docker_daemon,
              _ssh_host_key, _missing_interface, _read_only_filesystem)


def diagnose(script, output=None, platform_name=None):
    """Return factual diagnoses for supplied command output.

    No diagnosis is returned without output. A detector must recognise a
    specific fingerprint before it can say anything; unknown failures remain
    an explicit abstention.
    """
    if not isinstance(script, str):
        raise TypeError('script must be a string')
    if output is not None and not isinstance(output, str):
        raise TypeError('output must be a string or None')
    if platform_name is None:
        platform_name = os.name
    if platform_name not in ('posix', 'nt'):
        raise ValueError("platform_name must be 'posix' or 'nt'")

    diagnoses = [] if output is None else [
        diagnosis for detector in _DETECTORS
        for diagnosis in (detector(script, output, platform_name),)
        if diagnosis is not None]
    return {
        'command': script,
        'output_supplied': output is not None,
        'decision': 'diagnose' if diagnoses else 'abstain',
        'diagnoses': diagnoses,
    }


def format_human(result):
    """Render a diagnosis without adding facts to it."""
    if not result['output_supplied']:
        return 'No captured output; nothing deterministic to explain.'
    if not result['diagnoses']:
        return 'No deterministic diagnosis found.'

    lines = []
    for diagnosis in result['diagnoses']:
        lines.append(diagnosis['summary'])
        lines.extend('  evidence  {}'.format(value)
                     for value in diagnosis['evidence'])
        lines.extend(
            '  next      {} ({}, {})'.format(
                step['command'], step['reason'], step['risk'])
            for step in diagnosis['next_steps'])
    return '\n'.join(lines)
