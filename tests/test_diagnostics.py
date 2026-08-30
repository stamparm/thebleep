# -*- coding: utf-8 -*-

"""Real failure fingerprints, with no shell or machine probing.

The examples below are the final lines captured from real commands: Python's
second bind to an occupied local port, importing a missing Python module,
``df``/filesystem failures, refused/reset/timed-out TCP connections, TLS
verification, and DNS resolution failures from curl, Node.js, and Python.
Only the stable wording is kept; paths, tracebacks and host-specific details
are intentionally not part of the contract.
"""

import pytest

from thebleep import diagnostics


def test_address_in_use_extracts_port_and_offers_read_only_next_step():
    result = diagnostics.diagnose(
        'python server.py --port 5432',
        'OSError: [Errno 98] Address already in use',
        platform_name='posix')

    assert result == {
        'command': 'python server.py --port 5432',
        'output_supplied': True,
        'decision': 'diagnose',
        'diagnoses': [{
            'kind': 'address_in_use',
            'summary': 'Port 5432 is already in use.',
            'evidence': ['address already in use', 'port 5432'],
            'next_steps': [{
                'command': 'lsof -nP -iTCP:5432 -sTCP:LISTEN',
                'reason': 'find the process listening on this port',
                'risk': 'read-only'}]}]}


def test_dns_failure_extracts_host_and_offers_read_only_next_step():
    result = diagnostics.diagnose(
        'curl http://this-host-does-not-exist.invalid/',
        'curl: (6) Could not resolve host: '
        'this-host-does-not-exist.invalid\n',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'dns_failure',
        'summary': 'The hostname could not be resolved.',
        'evidence': ['could not resolve host: '
                     'this-host-does-not-exist.invalid'],
        'next_steps': [{
            'command': 'getent hosts this-host-does-not-exist.invalid',
            'reason': 'check whether DNS can resolve the hostname',
            'risk': 'read-only'}]}]


def test_curl_timeout_extracts_url_port_and_offers_route_inspection():
    """Captured from curlimages/curl latest against TEST-NET-1."""
    result = diagnostics.diagnose(
        'curl --connect-timeout 1 http://192.0.2.1:81/',
        'curl: (28) Connection timed out after 1000 milliseconds\n',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'connection_timeout',
        'summary': 'The connection timed out before a response arrived.',
        'evidence': ['connection timed out', 'port 81'],
        'next_steps': [{
            'command': 'netstat -rn',
            'reason': 'inspect the local routing table',
            'risk': 'read-only'}]}]


def test_connection_reset_extracts_url_port_and_checks_local_listener():
    """Captured from curl 8 against a local socket that closes immediately."""
    result = diagnostics.diagnose(
        'curl http://127.0.0.1:8765/',
        'curl: (56) Recv failure: Connection reset by peer\n',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'connection_reset',
        'summary': 'The peer closed the connection unexpectedly.',
        'evidence': ['recv failure: connection reset', 'port 8765'],
        'next_steps': [{
            'command': 'lsof -nP -iTCP:8765 -sTCP:LISTEN',
            'reason': 'check the local listener on this port',
            'risk': 'read-only'}]}]


def test_network_unreachable_uses_the_target_platform_route_command():
    """Captured from Python 3 in a container with networking disabled."""
    result = diagnostics.diagnose(
        'python -c "socket.connect((\'1.1.1.1\', 80))"',
        'OSError: [Errno 101] Network is unreachable',
        platform_name='nt')

    assert result['diagnoses'] == [{
        'kind': 'network_unreachable',
        'summary': 'The network could not reach the target.',
        'evidence': ['network is unreachable'],
        'next_steps': [{
            'command': 'route print',
            'reason': 'inspect the local routing table',
            'risk': 'read-only'}]}]


def test_dns_failure_quotes_host_for_powershell():
    result = diagnostics.diagnose(
        'curl https://example.test',
        'Could not resolve host: example.test;',
        platform_name='nt')

    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        "Resolve-DnsName 'example.test'")


def test_node_getaddrinfo_failure_extracts_host():
    """Captured from Node.js v26.8.1 resolving an invalid host."""
    result = diagnostics.diagnose(
        'node -e "dns.lookup(\'thebleep-inventory-no-such.invalid\')"',
        'Error: getaddrinfo ENOTFOUND thebleep-inventory-no-such.invalid',
        platform_name='posix')

    assert result['diagnoses'][0]['evidence'] == [
        'getaddrinfo enotfound thebleep-inventory-no-such.invalid']
    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        'getent hosts thebleep-inventory-no-such.invalid')


def test_python_temporary_dns_failure_extracts_host_from_command():
    """Captured from Python 3.14 in a container with networking disabled."""
    result = diagnostics.diagnose(
        'python -c "socket.getaddrinfo(\'example.test\', 80)"',
        'socket.gaierror: [Errno -3] Temporary failure in name resolution',
        platform_name='posix')

    assert result['diagnoses'][0]['evidence'] == [
        'temporary failure in name resolution']
    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        'getent hosts example.test')


def test_dns_failure_does_not_invent_a_host():
    result = diagnostics.diagnose(
        'tool', 'temporary failure in name resolution', platform_name='posix')

    assert result['diagnoses'][0]['next_steps'] == []


def test_dns_failure_extracts_host_from_url_when_output_has_no_host():
    result = diagnostics.diagnose(
        'curl https://example.test/api',
        'curl: (6) Could not resolve host',
        platform_name='posix')

    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        'getent hosts example.test')


def test_busybox_dns_failure_extracts_quoted_host():
    """Captured from BusyBox ping 1.37.0 in current Alpine."""
    result = diagnostics.diagnose(
        'ping -c 1 thebleep-inventory-no-such.invalid',
        "ping: bad address 'thebleep-inventory-no-such.invalid'\n",
        platform_name='posix')

    assert result['diagnoses'][0]['evidence'] == [
        "bad address 'thebleep-inventory-no-such.invalid'"]
    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        'getent hosts thebleep-inventory-no-such.invalid')


def test_read_only_filesystem_offers_only_a_mount_inspection():
    """Captured from ``touch`` in a read-only Alpine container."""
    result = diagnostics.diagnose(
        'touch /thebleep-inventory-file',
        'touch: /thebleep-inventory-file: Read-only file system\n',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'read_only_filesystem',
        'summary': 'The filesystem rejected the write because it is mounted '
                   'read-only.',
        'evidence': ['read-only file system'],
        'next_steps': [{
            'command': 'mount',
            'reason': 'inspect filesystem mount or volume state',
            'risk': 'read-only'}]}]


def test_exec_format_error_explains_a_directly_invoked_binary():
    """Captured from bash running a validly executable, foreign-format file."""
    result = diagnostics.diagnose(
        './badbin',
        'bash: ./badbin: cannot execute binary file: Exec format error',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'executable_format',
        'summary': 'The operating system cannot execute this file format.',
        'evidence': ['cannot execute binary file'],
        'next_steps': [{
            'command': 'file ./badbin',
            'reason': 'inspect the executable format and architecture',
            'risk': 'read-only'}]}]


def test_missing_interpreter_shows_the_script_declaration():
    """Captured from bash running a script with a nonexistent shebang."""
    result = diagnostics.diagnose(
        './script',
        'bash: ./script: cannot execute: required file not found',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'missing_interpreter',
        'summary': 'The script interpreter could not be found.',
        'evidence': ['cannot execute: required file not found'],
        'next_steps': [{
            'command': 'head -n 1 ./script',
            'reason': 'inspect the script interpreter declaration',
            'risk': 'read-only'}]}]


def test_launch_diagnoses_do_not_invent_an_inspection_target():
    result = diagnostics.diagnose(
        'python app.py', 'Exec format error', platform_name='posix')

    assert result['diagnoses'][0]['next_steps'] == []


def test_docker_daemon_failure_offers_only_a_read_only_check():
    result = diagnostics.diagnose(
        'docker compose ps',
        'ERROR: Cannot connect to the Docker daemon at '
        'unix:///tmp/thebleep-no-docker.sock. Is the docker daemon running?',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'docker_daemon_unavailable',
        'summary': 'Docker could not reach its daemon.',
        'evidence': ['cannot connect to the docker daemon'],
        'next_steps': [{
            'command': 'docker info',
            'reason': 'check whether the Docker daemon is reachable',
            'risk': 'read-only'}]}]


def test_ssh_host_key_failure_warns_before_any_key_removal():
    result = diagnostics.diagnose(
        'ssh user@example.test',
        'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!\n'
        'Host key for example.test has changed.',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'ssh_host_key_changed',
        'summary': 'SSH rejected the host key; verify the server identity.',
        'evidence': [
            'warning: remote host identification has changed!',
            'host example.test'],
        'next_steps': [{
            'command': 'ssh-keygen -F example.test',
            'reason': 'inspect the stored key before changing it',
            'risk': 'read-only'}]}]


def test_ssh_host_name_is_quoted_in_the_inspection_step():
    result = diagnostics.diagnose(
        'ssh user@host',
        'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!\n'
        'Host key for bad$(touch has changed.',
        platform_name='posix')

    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        "ssh-keygen -F 'bad$(touch'")


def test_missing_network_interface_lists_available_interfaces():
    result = diagnostics.diagnose(
        'ifconfig thebleep-no-such-interface',
        'ifconfig: interface thebleep-no-such-interface does not exist',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'missing_network_interface',
        'summary': "Network interface 'thebleep-no-such-interface' does not "
                   'exist.',
        'evidence': ['interface thebleep-no-such-interface does not exist'],
        'next_steps': [{
            'command': 'ifconfig -a',
            'reason': 'list the available network interfaces',
            'risk': 'read-only'}]}]


def test_linux_ifconfig_missing_interface_is_explained():
    """Linux and BusyBox use a different real error than BSD ifconfig."""
    result = diagnostics.diagnose(
        'ifconfig thebleep-no-such-interface',
        'thebleep-no-suc: error fetching interface information: '
        'Device not found\n',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'missing_network_interface',
        'summary': "Network interface 'thebleep-no-such-interface' does not "
                   'exist.',
        'evidence': ['thebleep-no-suc: error fetching interface information: '
                     'device not found'],
        'next_steps': [{
            'command': 'ifconfig -a',
            'reason': 'list the available network interfaces',
            'risk': 'read-only'}]}]


@pytest.mark.parametrize('output, path', [
    ("cp: can't create 'missing-dir/destination': No such file or "
     'directory\n', 'missing-dir/destination'),
    ("cp: can't stat 'missing-source': No such file or directory\n",
     'missing-source'),
    ("mkdir: can't create directory 'missing-dir/destination': No such "
     'file or directory\n', 'missing-dir/destination'),
    ("mv: can't rename 'thebleep-source': No such file or directory\n",
     'thebleep-source'),
])
def test_busybox_missing_paths_are_explained(output, path):
    """BusyBox's real wording uses ``can't`` instead of ``cannot``."""
    result = diagnostics.diagnose('tool {}'.format(path), output,
                                  platform_name='posix')

    assert result['diagnoses'][0]['kind'] == 'missing_path'
    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        'ls -ld {}'.format(path))


def test_windows_posix_tool_missing_path_is_explained():
    """Git for Windows emits POSIX utility errors on an NT host."""
    result = diagnostics.diagnose(
        'mkdir missing-dir/destination',
        "/usr/bin/mkdir: cannot create directory 'missing-dir/destination': "
        'No such file or directory\n',
        platform_name='nt')

    assert result['diagnoses'][0]['kind'] == 'missing_path'
    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        "Get-Item -LiteralPath 'missing-dir/destination'")


def test_git_outside_a_repository_is_explained():
    result = diagnostics.diagnose(
        'git status',
        'fatal: not a git repository (or any of the parent directories): .git',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'git_not_repository',
        'summary': 'Git could not find a repository here or in a parent '
                   'directory.',
        'evidence': ['not a git repository'],
        'next_steps': [{
            'command': 'pwd',
            'reason': 'check the directory where the command is running',
            'risk': 'read-only'}]}]


def test_python_missing_path_is_explained_and_quoted():
    result = diagnostics.diagnose(
        'python app.py',
        "FileNotFoundError: [Errno 2] No such file or directory: "
        "'/tmp/a; touch /tmp/bleep-owned'",
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'missing_path',
        'summary': 'Python could not find the requested path.',
        'evidence': ['no such file or directory'],
        'next_steps': [{
            'command': "ls -ld '/tmp/a; touch /tmp/bleep-owned'",
            'reason': 'check whether the requested path exists',
                   'risk': 'read-only'}]}]


@pytest.mark.parametrize('platform_name, output, command', [
    ('posix', 'ln: existing: File exists', 'ls -ld existing'),
    ('nt', "/usr/bin/ln: failed to create symbolic link 'existing': "
           'File exists', "Get-Item -LiteralPath 'existing'")])
def test_existing_path_is_explained_with_a_safe_inspection(
        platform_name, output, command):
    result = diagnostics.diagnose(
        'ln -s missing existing', output, platform_name=platform_name)

    assert result['diagnoses'][0]['kind'] == 'path_already_exists'
    assert result['diagnoses'][0]['next_steps'][0]['command'] == command
    assert result['diagnoses'][0]['next_steps'][0]['risk'] == 'read-only'


def test_python_permission_path_gets_a_safe_inspection_step():
    result = diagnostics.diagnose(
        'python app.py',
        "PermissionError: [Errno 13] Permission denied: "
        "'/tmp/a; chmod 777 /tmp/bleep-owned'",
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'permission_denied',
        'summary': 'The operating system denied the operation.',
        'evidence': ['permission denied'],
        'next_steps': [{
            'command': "ls -ld '/tmp/a; chmod 777 /tmp/bleep-owned'",
            'reason': 'inspect permissions on the denied path',
            'risk': 'read-only'}]}]


def test_posix_permission_path_gets_a_safe_inspection_step():
    result = diagnostics.diagnose(
        'cat /proc/1/mem',
        'cat: /proc/1/mem: Permission denied',
        platform_name='posix')

    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        'ls -ld /proc/1/mem')


def test_posix_permission_path_is_quoted():
    result = diagnostics.diagnose(
        'cat /tmp/config',
        "cat: '/tmp/a; touch /tmp/bleep-owned': Permission denied",
        platform_name='posix')

    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        "ls -ld '/tmp/a; touch /tmp/bleep-owned'")


def test_posix_missing_path_gets_a_safe_inspection_step():
    result = diagnostics.diagnose(
        'ls /tmp/bleep-does-not-exist',
        'ls: cannot access /tmp/bleep-does-not-exist: '
        'No such file or directory',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'missing_path',
        'summary': 'The requested path does not exist.',
        'evidence': ['no such file or directory'],
        'next_steps': [{
            'command': 'ls -ld /tmp/bleep-does-not-exist',
            'reason': 'check whether the requested path exists',
            'risk': 'read-only'}]}]


def test_posix_missing_path_is_quoted():
    result = diagnostics.diagnose(
        'ls /tmp/config',
        "ls: cannot access '/tmp/a; touch /tmp/bleep-owned': "
        'No such file or directory',
        platform_name='posix')

    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        "ls -ld '/tmp/a; touch /tmp/bleep-owned'")


def test_bsd_mv_missing_path_checks_both_sides_of_rename():
    """macOS reports both operands, but not which one was absent."""
    result = diagnostics.diagnose(
        'mv thebleep-source missing-dir/destination',
        'mv: rename thebleep-source to missing-dir/destination: '
        'No such file or directory',
        platform_name='posix')

    assert [step['command'] for step in result['diagnoses'][0]['next_steps']] \
        == ['ls -ld thebleep-source', 'ls -ld missing-dir/destination']


def test_git_conflict_offers_status_as_a_read_only_next_step():
    result = diagnostics.diagnose(
        'git merge feature',
        'Auto-merging file.txt\n'
        'CONFLICT (content): Merge conflict in file.txt\n'
        'Automatic merge failed; fix conflicts and then commit the result.',
        platform_name='posix')

    assert result['diagnoses'] == [{
        'kind': 'git_conflict',
        'summary': 'Git stopped because changes conflict.',
        'evidence': ['conflict (content): merge conflict in file.txt'],
        'next_steps': [{
            'command': 'git status --short',
            'reason': 'list the files that need attention',
            'risk': 'read-only'}]}]


@pytest.mark.parametrize('kind, script, output, command', [
    ('address_in_use', 'python server.py --port 5432',
     'OSError: [WinError 10048] Address already in use',
     'netstat -ano -p tcp | findstr ":5432"'),
    ('connection_refused', 'python client.py --port 8080',
     'ConnectionRefusedError: [WinError 10061] Connection refused',
     'netstat -ano -p tcp | findstr ":8080"'),
    ('certificate_expired', 'curl https://example.test',
     'certificate has expired', '[DateTime]::UtcNow'),
    ('disk_full', 'make', 'No space left on device',
     'Get-PSDrive -PSProvider FileSystem'),
    ('permission_denied', 'python app.py',
     r"PermissionError: [WinError 5] Access is denied: "
     r"'C:\\private\\config.ini'",
     r"Get-Acl -LiteralPath 'C:\private\config.ini'"),
    ('git_not_repository', 'git status',
     'fatal: not a git repository (or any of the parent directories): .git',
     'Get-Location'),
    ('missing_path', 'python app.py',
     r"FileNotFoundError: [WinError 2] The system cannot find the file "
     r"specified: 'C:\\missing\\config.ini'",
     r"Get-Item -LiteralPath 'C:\missing\config.ini'"),
    ('executable_format', r'C:\tools\bad.exe',
     'Exec format error', r"Get-Item -LiteralPath 'C:\tools\bad.exe'"),
    ('missing_interpreter', r'C:\tools\script', 'bad interpreter',
     r"Get-Content -LiteralPath 'C:\tools\script' -TotalCount 1"),
])
def test_windows_diagnostics_offer_windows_read_only_next_steps(
        kind, script, output, command):
    result = diagnostics.diagnose(script, output, platform_name='nt')

    diagnosis = next(item for item in result['diagnoses']
                     if item['kind'] == kind)
    assert diagnosis['next_steps'][0]['command'] == command


@pytest.mark.parametrize('script, output, kind, summary', [
    ('cat /root/file', 'Permission denied', 'permission_denied',
     'The operating system denied the operation.'),
    ('curl https://example.test', 'certificate has expired',
     'certificate_expired',
     'The peer certificate could not be trusted because it is expired.'),
    ('make', 'No space left on device', 'disk_full',
     'The filesystem is out of space.'),
    ('python client.py --port 8080',
     'ConnectionRefusedError: [Errno 111] Connection refused',
     'connection_refused',
     'The target refused the connection on port 8080.'),
    ('curl http://192.0.2.1:81/',
     'curl: (28) Connection timed out after 1000 milliseconds',
     'connection_timeout',
     'The connection timed out before a response arrived.'),
    ('python app.py', "ModuleNotFoundError: No module named 'tomli'",
     'missing_python_module', "Python could not import module 'tomli'."),
    ('git status',
     "fatal: detected dubious ownership in repository at '/tmp/project'",
     'git_dubious_ownership',
     'Git refused to trust this repository ownership.'),
    ('git status',
     'fatal: not a git repository (or any of the parent directories): .git',
     'git_not_repository',
     'Git could not find a repository here or in a parent directory.'),
    ('docker ps',
     'Cannot connect to the Docker daemon at unix:///var/run/docker.sock. '
     'Is the docker daemon running?',
     'docker_daemon_unavailable',
     'Docker could not reach its daemon.'),
    ('ssh user@example.test',
     'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!\n'
     'Host key for example.test has changed.',
     'ssh_host_key_changed',
     'SSH rejected the host key; verify the server identity.'),
])
def test_known_failures_are_named_without_guessing(script, output, kind,
                                                   summary):
    result = diagnostics.diagnose(script, output)

    assert result['decision'] == 'diagnose'
    assert result['diagnoses'][0]['kind'] == kind
    assert result['diagnoses'][0]['summary'] == summary


def test_unknown_failure_abstains():
    result = diagnostics.diagnose('my-command', 'something went wrong')

    assert result == {
        'command': 'my-command',
        'output_supplied': True,
        'decision': 'abstain',
        'diagnoses': []}


def test_other_certificate_verification_failures_are_not_called_expired():
    result = diagnostics.diagnose('curl https://example.test',
                                  'certificate verify failed: hostname')

    assert result['decision'] == 'abstain'


def test_missing_output_abstains_without_collecting_it():
    assert diagnostics.diagnose('my-command') == {
        'command': 'my-command',
        'output_supplied': False,
        'decision': 'abstain',
        'diagnoses': []}


@pytest.mark.parametrize('script, output, message', [
    (['python'], '', 'script must be a string'),
    ('python', b'error', 'output must be a string or None'),
])
def test_requires_text(script, output, message):
    with pytest.raises(TypeError, match=message):
        diagnostics.diagnose(script, output)


def test_platform_name_is_explicitly_limited():
    with pytest.raises(
            ValueError, match="platform_name must be 'posix' or 'nt'"):
        diagnostics.diagnose('python', 'error', platform_name='darwin')
