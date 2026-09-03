# -*- encoding: utf-8 -*-

"""Running a correction without asking, when there is enough to go on.

`--yes` says run whatever comes first. `require_confirmation` says always ask.
Between them there was nothing, and the gap is where most corrections live: git
printed `the most similar command is status`, the correction is `git status`,
and the question at the prompt is a formality with the answer already on the
screen.

`auto_run_confidence` is a threshold. A correction runs without the prompt only
when all of these hold:

- the setting is on -- it is off by default, and a number has to be chosen;
- the correction's confidence is at least the threshold. The scores are the
  ones `--json` and `?` already show: 0.98 for a correction the user taught,
  0.95 for a rule that read the tool's own output, 0.75 for a rule that saw
  the command alone, and whatever a rule stated for itself through
  `Suggestion`. So `0.9` means "only when something more than the command was
  read", and `0.7` means "the ordinary guesses too";
- the risk scan found nothing: no `sudo`, no `rm`, no `--force`, no side effect.
  That scan is a review hint and not a proof, which is why it is a gate here
  and not the whole decision.

Everything else is asked about as before. Nothing here changes what is
suggested, only whether a keystroke stands between a good suggestion and its
run, and the line printed when one runs says which of these let it through.

"""

from . import risk
from .conf import settings


class Verdict(object):
    """Whether a correction may run unasked, and the reason either way."""

    __slots__ = ('allowed', 'reason', 'score', 'threshold')

    def __init__(self, allowed, reason, score=None, threshold=None):
        self.allowed = allowed
        self.reason = reason
        self.score = score
        self.threshold = threshold

    def __bool__(self):
        return self.allowed


def threshold(value=None):
    """The configured threshold as a float in (0, 1], or None when off.

    Read out of the settings unless given. Anything that is not a number in
    that range is off -- a threshold of zero or more than one would either run
    everything or nothing, and neither is what somebody typing a number meant.

    """
    if value is None:
        value = settings.auto_run_confidence
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 0 < number <= 1:
        return None
    return number


def decide(corrected_command, command=None):
    """Whether `corrected_command` may run without confirmation.

    :type corrected_command: thebleep.types.CorrectedCommand
    :type command: thebleep.types.Command | None
    :rtype: Verdict

    """
    limit = threshold()
    if limit is None:
        return Verdict(False, 'auto_run_confidence is off')

    from .explain import confidence

    assessed = confidence(getattr(corrected_command, 'rule', None),
                          command, corrected_command)
    score = assessed['score']
    if score is None:
        return Verdict(False, 'the suggestion has no confidence to compare',
                       score, limit)
    if score < limit:
        return Verdict(False, u'{}% confidence is under the {}% threshold'.format(
            _percent(score), _percent(limit)), score, limit)

    assessed_risk = risk.assess(corrected_command)
    if assessed_risk['factors']:
        return Verdict(False, u'risk: {}'.format(
            ', '.join(assessed_risk['factors'])), score, limit)

    rule = getattr(corrected_command, 'rule', None)
    if getattr(rule, 'learning_shipped', False):
        # A correction that came with a repository is somebody else's word.
        # It scores as high as one the user taught, and that is exactly why
        # it is never run without the prompt: a clone must not be able to
        # make a typo run its own script.
        return Verdict(False, 'the correction came with the repository, '
                              'not from you', score, limit)

    basis = assessed.get('basis') or ()
    reason = u'{}% confidence, {}; nothing risky in it'.format(
        _percent(score), basis[0] if basis else 'no basis given')
    return Verdict(True, reason, score, limit)


def _percent(fraction):
    return int(round(fraction * 100))
