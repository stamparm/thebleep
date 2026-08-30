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


SCHEMA_VERSION = 2
MAX_OUTPUT = 8 * 1024 * 1024


def _confidence(rule, command):
    """Return a useful score alongside the human-readable confidence tier.

    The number is an ordinal heuristic, not a probability. It deliberately
    rewards evidence the engine can point to: an accepted learned correction is
    stronger than a rule match, and a captured tool error is stronger than a
    command-only guess.
    """
    if rule is None:
        return {
            'level': 'unknown',
            'score': None,
            'basis': ['the suggestion did not identify its rule'],
        }
    if getattr(rule, 'learned', False):
        return {
            'level': 'high',
            'score': 0.98,
            'basis': ['a correction learned from the user'],
        }
    if rule.requires_output and command.output is not None:
        return {
            'level': 'high',
            'score': 0.95,
            'basis': ['the rule matched captured command output'],
        }
    return {
        'level': 'medium',
        'score': 0.75,
        'basis': ['the rule matched the command or local context'],
    }


def _evidence_details(explanation):
    kinds = {
        'rule': 'source',
        'matched': 'match',
        'read': 'context',
        'side effect': 'side_effect',
        'runs as': 'execution',
    }
    return [{'kind': kinds.get(label, label), 'text': value}
            for label, value in explanation]


def _check_output(output):
    if output is not None and len(output.encode('utf-8')) > MAX_OUTPUT:
        raise ValueError('output exceeds the 8 MiB limit')


def _check_script(script):
    if not script.strip():
        raise ValueError('script must be a non-empty command')
    if '\x00' in script:
        raise ValueError('script must not contain NUL bytes')


def _suggestion(corrected, command):
    rule = getattr(corrected, 'rule', None)
    explanation = explain_module.describe(corrected, command)
    assessment = risk.assess(corrected)
    confidence = _confidence(rule, command)
    return {
        'command': corrected.script,
        'rule': rule.name if rule is not None else None,
        'priority': corrected.priority,
        'confidence': confidence,
        'side_effect': bool(corrected.side_effect),
        'risk': assessment['level'],
        'risk_factors': assessment['factors'],
        'requires_output': bool(rule and rule.requires_output),
        'evidence': [
            value for label, value in explanation
            if label in ('matched', 'read')],
        'evidence_details': _evidence_details(explanation),
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
    _check_script(script)
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
        'structure': command.command_model.as_dict(),
        'output_supplied': output is not None,
        'decision': 'suggest' if suggestions else 'abstain',
        'suggestions': suggestions,
    }


def why(script, output=None, platform_name=None):
    """Return deterministic diagnoses for output the caller already has."""
    if not isinstance(script, str):
        raise TypeError('script must be a string')
    _check_script(script)
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
        'structure': Command(script, output).command_model.as_dict(),
        'output_supplied': result['output_supplied'],
        'decision': result['decision'],
        'diagnoses': result['diagnoses'],
    }
