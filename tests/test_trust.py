# -*- encoding: utf-8 -*-

"""`auto_run_confidence`: a correction runs unasked only past every gate."""

import pytest
from thebleep import trust
from thebleep.types import Command, CorrectedCommand, Rule, Suggestion


def rule(name='some_rule', requires_output=False):
    return Rule(name, lambda _: True, lambda _: 'x', True, None, 1000,
                requires_output)


class TestThreshold(object):
    @pytest.mark.parametrize('value, expected', [
        (None, None), (False, None), (True, None),
        (0, None), (0.0, None), (1.5, None), (-0.5, None), ('abc', None),
        (0.5, 0.5), (1, 1.0), ('0.9', 0.9),
    ])
    def test_only_a_share_of_one_counts(self, value, expected):
        assert trust.threshold(value) == expected

    def test_read_from_settings(self, settings):
        settings.auto_run_confidence = 0.8
        assert trust.threshold() == 0.8
        settings.auto_run_confidence = None
        assert trust.threshold() is None


class TestDecide(object):
    @pytest.fixture
    def command(self):
        return Command('git satus', 'git: satus is not a git command')

    def test_off_by_default(self, settings, command):
        settings.auto_run_confidence = None
        verdict = trust.decide(
            CorrectedCommand('git status', None, 1000,
                             rule=rule(requires_output=True)), command)
        assert not verdict
        assert 'off' in verdict.reason

    def test_a_rule_that_read_the_output_passes_at_ninety(
            self, settings, command):
        settings.auto_run_confidence = 0.9
        verdict = trust.decide(
            CorrectedCommand('git status', None, 1000,
                             rule=rule(requires_output=True)), command)
        assert verdict
        assert verdict.score == 0.95
        assert 'captured command output' in verdict.reason

    def test_a_command_only_guess_does_not(self, settings, command):
        settings.auto_run_confidence = 0.9
        verdict = trust.decide(
            CorrectedCommand('git status', None, 1000, rule=rule()), command)
        assert not verdict
        assert 'under the 90% threshold' in verdict.reason

    def test_unless_the_threshold_says_so(self, settings, command):
        settings.auto_run_confidence = 0.7
        assert trust.decide(
            CorrectedCommand('git status', None, 1000, rule=rule()), command)

    def test_a_rule_that_needs_output_it_never_got_is_a_guess(self, settings):
        """`requires_output` with no output is scored as a guess, and the
        threshold that admits captured output keeps it out."""
        settings.auto_run_confidence = 0.9
        assert not trust.decide(
            CorrectedCommand('git status', None, 1000,
                             rule=rule(requires_output=True)),
            Command('git satus', None))

    @pytest.mark.parametrize('script', [
        'sudo git status', 'rm -rf build', 'git push --force', 'doas ls'])
    def test_a_risk_marker_refuses(self, settings, command, script):
        settings.auto_run_confidence = 0.9
        verdict = trust.decide(
            CorrectedCommand(script, None, 1000,
                             rule=rule(requires_output=True)), command)
        assert not verdict
        assert verdict.reason.startswith('risk:')

    def test_a_side_effect_refuses(self, settings, command):
        settings.auto_run_confidence = 0.9
        verdict = trust.decide(
            CorrectedCommand('git status', lambda *_: None, 1000,
                             rule=rule(requires_output=True)), command)
        assert not verdict
        assert 'side effect' in verdict.reason

    def test_a_learned_correction_passes(self, settings, command):
        settings.auto_run_confidence = 0.95
        learned = rule()
        learned.learned = True
        assert trust.decide(
            CorrectedCommand('git status', None, 50, rule=learned), command)

    def test_a_rule_that_states_its_own_confidence(self, settings, command):
        settings.auto_run_confidence = 0.9
        sure = Suggestion('git status', confidence=0.93, evidence=('git said',))
        assert trust.decide(
            CorrectedCommand(str(sure), None, 1000, rule=rule(),
                             confidence=sure.confidence,
                             evidence=sure.evidence), command)
        unsure = CorrectedCommand('git status', None, 1000, rule=rule(),
                                  confidence=0.6)
        assert not trust.decide(unsure, command)

    def test_no_rule_means_no_confidence_and_no_run(self, settings, command):
        settings.auto_run_confidence = 0.1
        verdict = trust.decide(CorrectedCommand('git status', None, 1000),
                               command)
        assert not verdict
        assert 'no confidence' in verdict.reason


def test_a_correction_the_repository_ships_is_never_run_unasked(settings):
    """It scores as high as one the user taught, and that is exactly why: a
    clone must not be able to make a typo run its own script."""
    settings.auto_run_confidence = 0.5
    shipped = rule()
    shipped.learned = True
    shipped.learning_shipped = True
    verdict = trust.decide(
        CorrectedCommand('git status', None, 50, rule=shipped),
        Command('gti status', None))
    assert not verdict
    assert 'came with the repository' in verdict.reason
