# -*- coding: utf-8 -*-

"""Real failure fingerprints, with no shell or machine probing.

The examples below are the final lines captured from real commands: Python's
second bind to an occupied local port, importing a missing Python module,
``df``/filesystem failures, a refused TCP connection, and TLS verification.
Only the stable wording is kept; paths, tracebacks and host-specific details
are intentionally not part of the contract.
"""

import pytest

from thebleep import diagnostics


def test_address_in_use_extracts_port_and_offers_read_only_next_step():
    result = diagnostics.diagnose(
        'python server.py --port 5432',
        'OSError: [Errno 98] Address already in use')

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
    ('python app.py', "ModuleNotFoundError: No module named 'tomli'",
     'missing_python_module', "Python could not import module 'tomli'."),
    ('git status',
     "fatal: detected dubious ownership in repository at '/tmp/project'",
     'git_dubious_ownership',
     'Git refused to trust this repository ownership.'),
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
