# -*- encoding: utf-8 -*-

"""A structured, non-executing interface to the correction engine.

The command-line entry point is deliberately tied to shell state: it reads a
previous command, may capture its output, and eventually prints text for the
shell to execute. Editors, IDEs and agents need a smaller contract. They can
hand The Bleep the command and any output they already have, then inspect plain
Python data without starting a shell or accepting a correction. Helper-process
probes are disabled here too; an API caller never causes a program from the
supplied command line to run.

When `output` is omitted, only rules that do not require output can match. The
engine is never asked to replay the command on behalf of this API.
"""

from . import explain as explain_module
from .corrector import get_corrected_commands
from .types import Command
from . import diagnostics, risk
from .utils import tool_probes


SCHEMA_VERSION = 1
MAX_OUTPUT = 8 * 1024 * 1024


def _check_output(output):
    if output is not None and len(output.encode('utf-8')) > MAX_OUTPUT:
        raise ValueError('output exceeds the 8 MiB limit')


def _suggestion(corrected, command):
    rule = getattr(corrected, 'rule', None)
    explanation = explain_module.describe(corrected, command)
    assessment = risk.assess(corrected)
    return {
        'command': corrected.script,
        'rule': rule.name if rule is not None else None,
        'priority': corrected.priority,
        'side_effect': bool(corrected.side_effect),
        'risk': assessment['level'],
        'risk_factors': assessment['factors'],
        'requires_output': bool(rule and rule.requires_output),
        'evidence': [
            value for label, value in explanation
            if label in ('matched', 'read')],
        'explanation': [
            {'label': label, 'value': value}
            for label, value in explanation],
    }


def suggest(script, output=None):
    """Return deterministic correction data for ``script``.

    ``output`` should be the output the caller already captured. It is not
    collected here, so calling this function cannot run the user's command.

    :param script: command line to correct
    :param output: captured command output, or ``None`` when unavailable
    :rtype: dict
    """
    if not isinstance(script, str):
        raise TypeError('script must be a string')
    if output is not None and not isinstance(output, str):
        raise TypeError('output must be a string or None')
    _check_output(output)

    command = Command(script, output)
    with tool_probes(False):
        suggestions = [
            _suggestion(corrected, command)
            for corrected in get_corrected_commands(command)]
    return {
        'schema': SCHEMA_VERSION,
        'command': script,
        'output_supplied': output is not None,
        'decision': 'suggest' if suggestions else 'abstain',
        'suggestions': suggestions,
    }


def why(script, output=None, platform_name=None):
    """Return deterministic diagnoses for output the caller already has."""
    if not isinstance(script, str):
        raise TypeError('script must be a string')
    if output is not None and not isinstance(output, str):
        raise TypeError('output must be a string or None')
    _check_output(output)

    result = diagnostics.diagnose(script, output, platform_name)
    result['schema'] = SCHEMA_VERSION
    # Keep the top-level contract fields in the same order as `suggest`, even
    # though JSON consumers should treat object order as insignificant.
    return {
        'schema': result['schema'],
        'command': result['command'],
        'output_supplied': result['output_supplied'],
        'decision': result['decision'],
        'diagnoses': result['diagnoses'],
    }
