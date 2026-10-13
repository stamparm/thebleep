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


def test_powershell_names_count_too():
    """The PowerShell driver runs corrections through `Invoke-Expression`, and
    `Remove-Item` deletes as surely as `rm` does."""
    for script, factor in [
            ('Remove-Item -Recurse build', 'destructive command'),
            ('ri build', 'destructive command'),
            ('Clear-Content notes.txt', 'destructive command'),
            ('iex $payload', 'code execution'),
            ('Copy-Item a b -Force', 'safety bypass'),
            ('Start-Process pwsh -Verb RunAs', 'privilege escalation')]:
        assert factor in assess(CorrectedCommand(script, None, 100))['factors']
    assert assess(CorrectedCommand('git push --force-with-lease', None, 100))[
        'factors'] == ['safety bypass']
    assert assess(CorrectedCommand('git riff', None, 100))['factors'] == []
