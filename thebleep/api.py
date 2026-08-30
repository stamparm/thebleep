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

from difflib import SequenceMatcher

from . import explain as explain_module
from .corrector import get_corrected_commands
from .types import Command
from . import diagnostics, failure_store, risk
from .utils import tool_probes


SCHEMA_VERSION = 2
MAX_OUTPUT = 8 * 1024 * 1024
# A pathological custom rule must not make a structured request spend an
# unbounded amount of time finding a pretty diff. Large scripts still get a
# correct, source-safe replacement; they simply do not get a fine-grained one.
MAX_EDIT_DIFF = 64 * 1024


def _confidence(corrected, rule, command):
    """Return a useful score alongside the human-readable confidence tier.

    The number is an ordinal heuristic, not a probability. It deliberately
    rewards evidence the engine can point to: an accepted learned correction is
    stronger than a rule match, and a captured tool error is stronger than a
    command-only guess.
    """
    return explain_module.confidence(rule, command, corrected)


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


def _leaf_tokens(segments):
    """Yield source tokens without also yielding their nested containers."""
    for segment in segments:
        for token in segment.tokens:
            if token.children:
                yield from _leaf_tokens(token.children)
            else:
                yield token


def _apply_edits(original, edits):
    """Apply edits from right to left, as an internal consistency check."""
    result = original
    for edit in reversed(edits):
        result = result[:edit['start']] + edit['replacement'] + \
            result[edit['end']:]
    return result


def _structured_edits(original, replacement, shell_name):
    """Find edits at complete shell-token boundaries when possible."""
    from .command_model import parse

    before = parse(original, shell_name)
    after = parse(replacement, shell_name)
    if not before.complete or not after.complete:
        return None

    old_tokens = tuple(_leaf_tokens(before.segments))
    new_tokens = tuple(_leaf_tokens(after.segments))
    if len(old_tokens) != len(new_tokens) or any(
            old.kind != new.kind for old, new in zip(old_tokens, new_tokens)):
        return None

    edits = [
        {'start': old.start, 'end': old.end, 'source': old.text,
         'replacement': new.text}
        for old, new in zip(old_tokens, new_tokens)
        if old.text != new.text
    ]
    return edits if _apply_edits(original, edits) == replacement else None


def _edits(original, replacement, shell_name='posix'):
    """Return deterministic source edits for an editor or agent.

    Each edit is independently applicable to ``original``. Including the
    original slice makes stale-buffer checks possible without re-parsing shell
    syntax. The bounded fallback is intentional: a whole-command replacement
    is safer than an expensive diff for an unusually large custom suggestion.
    """
    if max(len(original), len(replacement)) > MAX_EDIT_DIFF:
        return [{'start': 0, 'end': len(original),
                 'source': original, 'replacement': replacement}]

    structured = _structured_edits(original, replacement, shell_name)
    if structured is not None:
        return structured

    matcher = SequenceMatcher(a=original, b=replacement, autojunk=False)
    return [
        {'start': start, 'end': end, 'source': original[start:end],
         'replacement': replacement[new_start:new_end]}
        for tag, start, end, new_start, new_end in matcher.get_opcodes()
        if tag != 'equal'
    ]


def _suggestion(corrected, command):
    rule = getattr(corrected, 'rule', None)
    explanation = explain_module.describe(corrected, command)
    assessment = risk.assess(corrected)
    confidence = _confidence(corrected, rule, command)
    explicit_evidence = [value for value in getattr(corrected, 'evidence', ())
                         if value]
    evidence = explicit_evidence or [
        value for label, value in explanation if label in ('matched', 'read')]
    evidence_details = _evidence_details(explanation)
    return {
        'command': corrected.script,
        'edits': _edits(command.script, corrected.script,
                        command.command_model.shell),
        'rule': rule.name if rule is not None else None,
        'priority': corrected.priority,
        'confidence': confidence,
        'side_effect': bool(corrected.side_effect),
        'risk': assessment['level'],
        'risk_factors': assessment['factors'],
        'requires_output': bool(rule and rule.requires_output),
        'evidence': evidence,
        'evidence_details': evidence_details,
        'explanation': [
            {'label': label, 'value': value}
            for label, value in explanation],
    }


def _suggestion_order(suggestion):
    """Rank structured candidates by evidence, then legacy priority.

    The interactive selector still receives the correction engine's original
    priority order. API and MCP callers have no selector context, so a
    candidate backed by captured output should precede a command-only guess.
    Unknown sources sort last, and stable priority ordering keeps ties
    deterministic for existing consumers.
    """
    score = suggestion['confidence']['score']
    return (score is None, -(score if score is not None else 0),
            suggestion['priority'])


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
    structure = command.command_model
    if not structure.complete:
        return {
            'schema': SCHEMA_VERSION,
            'command': script,
            'structure': structure.as_dict(),
            'output_supplied': output is not None,
            'decision': 'abstain',
            'suggestions': [],
        }

    with tool_probes(False):
        suggestions = [
            _suggestion(corrected, command)
            for corrected in get_corrected_commands(command)]
    suggestions.sort(key=_suggestion_order)
    return {
        'schema': SCHEMA_VERSION,
        'command': script,
        'structure': structure.as_dict(),
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


def history():
    """Return the bounded local failure history without executing anything.

    Records are newest first and include the output already captured when the
    failure happened, so a caller can inspect or feed one back to ``suggest``
    or ``why`` without replaying it.
    """
    return {
        'schema': SCHEMA_VERSION,
        'limit': failure_store.LIMIT,
        'failures': failure_store.public_entries(),
    }
