# -*- encoding: utf-8 -*-

"""Why a suggestion is being made.

A correction is a command somebody is about to run, and "because a program said
so" is a poor reason to run anything. What is wanted before pressing return is
small and specific: which rule this came from, what it saw that made it fire,
whether it needed to run your command again to see it, and whether accepting it
does anything besides run the command.

Everything here is a fact rather than a description. The rule's name, where its
file came from, whether it declares `requires_output`, whether it has a
`side_effect` -- and then the two that carry most of the meaning, both read out
of the rule's own syntax tree by the same extraction the rule pack uses to
decide which rules to load at all:

- the apps it is about, from `@for_app('git', ...)`;
- the text it requires in the output, from the literals its `match` tests for.

Neither is a summary of what the rule does. They are the conditions the rule
itself states, quoted back, and if the pack got them wrong the rule would not
have been run in the first place. Nothing here reads the rule's body and tries
to say in English what it means, and no rule had to be given a hand-written
description for this to work.

"""

import os
from . import logs, risk
from .utils import without_control_sequences


def confidence(rule, command=None, corrected_command=None):
    """Return the ordinal confidence used by structured consumers."""
    explicit = getattr(corrected_command, 'confidence', None)
    if explicit is not None:
        return {
            'level': 'high' if explicit >= 0.9
            else 'medium' if explicit >= 0.7 else 'low',
            'score': explicit,
            'basis': list(getattr(corrected_command, 'evidence', ()))
            or ['the rule supplied an explicit confidence'],
        }
    if rule is None:
        return {'level': 'unknown', 'score': None,
                'basis': ['the suggestion did not identify its rule']}
    if getattr(rule, 'learned', False):
        return {'level': 'high', 'score': 0.98,
                'basis': ['a correction learned from the user']}
    if rule.requires_output and command is not None \
            and command.output is not None:
        return {'level': 'high', 'score': 0.95,
                'basis': ['the rule matched captured command output']}
    return {'level': 'medium', 'score': 0.75,
            'basis': ['the rule matched the command or local context']}


def _origin(path):
    """Whether this rule came with The Bleep, from the user, or from a package."""
    if not path:
        return 'from somewhere unrecorded'

    bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules')
    directory = os.path.dirname(os.path.abspath(path))
    if os.path.normcase(directory) == os.path.normcase(bundled):
        return 'bundled'

    parent = os.path.basename(os.path.dirname(directory))
    if parent.startswith('thebleep_contrib_'):
        return 'from the {} package'.format(parent)

    return 'one of your own'


def _metadata(rule):
    """What the rule declares about itself, read from its source.

    The same extraction the rule pack does, run again here rather than carried
    around: it costs parsing one short file, only when somebody asks why.

    """
    if getattr(rule, 'metadata', None) is not None:
        return rule.metadata

    path = getattr(rule, 'path', None)
    if not path:
        return {}

    from . import rulepack

    try:
        with open(str(path), 'rb') as handle:
            source = handle.read()
        return rulepack._extract_metadata(source, str(path))
    except Exception:
        return {}


def _matched_because(metadata, output):
    """What the rule required, in the words it required them in.

    A clause is a set of alternatives, any one of which satisfies it. Where the
    output is to hand, the alternative that is actually in it is the one quoted
    -- so this says what was found and not merely what would have done.

    """
    said = []
    for clause in metadata.get('output') or ():
        alternatives = [needle for needle, _ in clause]
        found = None
        if output:
            lowered = output.lower()
            for needle, case_insensitive in clause:
                haystack = lowered if case_insensitive else output
                if needle in haystack:
                    found = needle
                    break
        said.append(u'"{}"'.format(_short(
            found if found is not None else alternatives[0])))

    return said


# Long enough to recognise the message, short enough to stay on one line.
QUOTE_LENGTH = 60


def _short(text):
    """A needle as it would be read aloud: trimmed, and not the whole page."""
    text = ' '.join(text.split())
    if len(text) <= QUOTE_LENGTH:
        return text
    return text[:QUOTE_LENGTH - 1] + u'…'


def _listed(names):
    """`a`, `a or b`, `a, b or c`."""
    names = sorted(names)
    if len(names) == 1:
        return names[0]
    return u'{} or {}'.format(', '.join(names[:-1]), names[-1])


def describe(corrected_command, command=None, include_assessment=False):
    """Why this correction is being offered, as label and value pairs.

    :type corrected_command: thebleep.types.CorrectedCommand
    :rtype: [(str, str)]

    """
    rule = getattr(corrected_command, 'rule', None)
    lines = []
    if include_assessment:
        assessed = confidence(rule, command, corrected_command)
        score = assessed['score']
        confidence_text = (
            u'{}% {}'.format(round(score * 100), assessed['level'])
            if score is not None else assessed['level'])
        lines.append(('confidence', confidence_text))
        assessed_risk = risk.assess(corrected_command)
        risk_text = assessed_risk['level']
        if assessed_risk['factors']:
            risk_text += ' ({})'.format(', '.join(assessed_risk['factors']))
        lines.append(('risk', risk_text))
    if rule is None:
        lines.append((
            'rule', 'unknown -- this suggestion came from somewhere'
            ' that did not say which rule made it'))
        return lines

    metadata = _metadata(rule)
    lines.append(('rule', u'{} ({})'.format(rule.name, _origin(
        getattr(rule, 'path', None)))))

    if getattr(rule, 'learned', False):
        lines.append(('matched', u'your {} learned correction for {}'.format(
            rule.learning_scope, rule.learning_executable)))
    else:
        apps = metadata.get('apps')
        said = _matched_because(metadata, command.output if command else None)
        if apps and said:
            lines.append(('matched', u'{}, and output containing {}'.format(
                _listed(apps), ' and '.join(said))))
        elif apps:
            lines.append(('matched', u'{}, whatever it printed'.format(
                _listed(apps))))
        elif said:
            lines.append(('matched', u'output containing {}'.format(
                ' and '.join(said))))
        else:
            lines.append(('matched', u'a condition this rule works out for itself'))

    for evidence in getattr(corrected_command, 'evidence', ()):
        lines.append(('evidence', _short(without_control_sequences(evidence))))

    if rule.requires_output:
        if command is not None and command.output is None:
            lines.append(('read', 'nothing -- the output was not available'))
        else:
            lines.append(('read', 'what your command printed'))
    else:
        lines.append(('read', 'only the command you typed, not its output'))

    if corrected_command.side_effect:
        lines.append(('side effect',
                      'accepting this does something besides run the command'))

    first = corrected_command.script.split()
    if first and os.path.basename(first[0]) in ('sudo', 'doas'):
        lines.append(('runs as', 'another user -- the correction begins with'
                                 ' {}'.format(first[0])))

    return lines


def show(corrected_command, command=None):
    logs.explanation(describe(corrected_command, command))
