# -*- encoding: utf-8 -*-

"""Deterministic explanations for failures that are not command typos.

The correction rules answer "what should I have typed instead?". Some failures
are already valid commands, so a better answer is a small, factual diagnosis.
This module deliberately only reads the supplied output: it never probes the
machine, reruns the command, or turns an extracted value into an executable
action.
"""

import re
import shlex


_PORT_IN_OUTPUT = re.compile(
    r'(?:\bport(?:\s+|=)|:)([0-9]{1,5})\b', re.IGNORECASE)
_PORT_IN_COMMAND = re.compile(
    r'(?:--?port(?:=|\s+)|\s-p(?:\s+|=))([0-9]{1,5})\b', re.IGNORECASE)
_MODULE = re.compile(
    r"(?:ModuleNotFoundError: )?No module named ['\"]([^'\"]+)['\"]")


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


def _address_in_use(script, output):
    if not re.search(r'address already in use', output, re.IGNORECASE):
        return None

    port = _port(script, output)
    evidence = ['address already in use']
    next_steps = []
    if port:
        evidence.append('port {}'.format(port))
        next_steps.append(_step(
            'lsof -nP -iTCP:{} -sTCP:LISTEN'.format(port),
            'find the process listening on this port'))
    return {
        'kind': 'address_in_use',
        'summary': ('Port {} is already in use.'.format(port)
                    if port else 'A network address is already in use.'),
        'evidence': evidence,
        'next_steps': next_steps,
    }


def _permission_denied(script, output):
    if not re.search(r'(?:permission denied|access is denied)', output,
                     re.IGNORECASE):
        return None
    match = re.search(r'permission denied|access is denied', output,
                      re.IGNORECASE)
    return {
        'kind': 'permission_denied',
        'summary': 'The operating system denied the operation.',
        'evidence': [match.group(0).lower()],
        'next_steps': [],
    }


def _certificate_expired(script, output):
    if not re.search(r'certificate has expired', output, re.IGNORECASE):
        return None
    match = re.search(r'certificate has expired', output, re.IGNORECASE)
    return {
        'kind': 'certificate_expired',
        'summary': 'The peer certificate could not be trusted because it is '
                   'expired.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step('date -u', 'check the local clock')],
    }


def _disk_full(script, output):
    if not re.search(r'no space left on device|disk full', output,
                     re.IGNORECASE):
        return None
    match = re.search(r'no space left on device|disk full', output,
                      re.IGNORECASE)
    return {
        'kind': 'disk_full',
        'summary': 'The filesystem is out of space.',
        'evidence': [match.group(0).lower()],
        'next_steps': [_step('df -h', 'inspect filesystem capacity')],
    }


def _connection_refused(script, output):
    if not re.search(r'connection refused', output, re.IGNORECASE):
        return None
    match = re.search(r'connection refused', output, re.IGNORECASE)
    port = _port(script, output)
    evidence = [match.group(0).lower()]
    next_steps = []
    if port:
        evidence.append('port {}'.format(port))
        next_steps.append(_step(
            'lsof -nP -iTCP:{} -sTCP:LISTEN'.format(port),
            'check whether anything is listening on this port'))
    return {
        'kind': 'connection_refused',
        'summary': ('The target refused the connection on port {}.'.format(
            port) if port else 'The target refused the connection.'),
        'evidence': evidence,
        'next_steps': next_steps,
    }


def _missing_module(script, output):
    match = _MODULE.search(output)
    if not match:
        return None
    module = match.group(1)
    return {
        'kind': 'missing_python_module',
        'summary': 'Python could not import module {!r}.'.format(module),
        'evidence': ["No module named '{}'".format(module)],
        'next_steps': [_step(
            'python -m pip show {}'.format(shlex.quote(module)),
            'check whether a distribution with this name is installed')],
    }


_DETECTORS = (_address_in_use, _permission_denied, _certificate_expired,
              _disk_full, _connection_refused, _missing_module)


def diagnose(script, output=None):
    """Return factual diagnoses for supplied command output.

    No diagnosis is returned without output. A detector must recognise a
    specific fingerprint before it can say anything; unknown failures remain
    an explicit abstention.
    """
    if not isinstance(script, str):
        raise TypeError('script must be a string')
    if output is not None and not isinstance(output, str):
        raise TypeError('output must be a string or None')

    diagnoses = [] if output is None else [
        diagnosis for detector in _DETECTORS
        for diagnosis in (detector(script, output),)
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
