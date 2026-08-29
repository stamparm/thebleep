from thebleep.risk import assess
from thebleep.types import CorrectedCommand


def test_ordinary_correction_has_no_known_risk_marker():
    result = assess(CorrectedCommand('git status', None, 100))

    assert result == {'level': 'low', 'factors': []}


def test_risk_markers_are_reported_in_stable_order():
    result = assess(CorrectedCommand(
        'sudo git push --force', None, 100))

    assert result == {
        'level': 'high',
        'factors': ['privilege escalation', 'safety bypass']}


def test_side_effects_are_high_risk_even_without_a_marker():
    result = assess(CorrectedCommand(
        'git status', lambda *_: None, 100))

    assert result == {'level': 'high', 'factors': ['side effect']}
