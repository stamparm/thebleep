from thebleep import api
from thebleep.types import CorrectedCommand
import pytest


class Rule(object):
    name = 'test_rule'
    path = None
    requires_output = True


def test_suggest_returns_structured_correction(mocker):
    correction = CorrectedCommand(
        'git status', None, 1200, rule=Rule())
    mocker.patch.object(api, 'get_corrected_commands',
                        return_value=iter([correction]))

    result = api.suggest('gti status', 'command not found')

    assert result == {
        'schema': 1,
        'command': 'gti status',
        'output_supplied': True,
        'decision': 'suggest',
        'suggestions': [{
            'command': 'git status',
            'rule': 'test_rule',
            'priority': 1200,
            'confidence': {
                'level': 'high',
                'basis': ['the rule matched captured command output']},
            'side_effect': False,
            'risk': 'low',
            'risk_factors': [],
            'requires_output': True,
            'evidence': [
                'a condition this rule works out for itself',
                'what your command printed'],
            'explanation': [
                {'label': 'rule', 'value': 'test_rule (from somewhere unrecorded)'},
                {'label': 'matched',
                 'value': 'a condition this rule works out for itself'},
                {'label': 'read', 'value': 'what your command printed'}],
        }],
    }


def test_suggest_does_not_collect_missing_output(mocker):
    corrections = mocker.patch.object(
        api, 'get_corrected_commands', return_value=iter([]))

    result = api.suggest('gti status')

    corrections.assert_called_once()
    assert result['output_supplied'] is False
    assert result['decision'] == 'abstain'
    assert result['suggestions'] == []


def test_suggest_does_not_run_helper_probes(mocker):
    from thebleep import utils

    def corrections(_):
        assert utils.tool_lines(['helper']) == []
        return iter([])

    mocker.patch.object(api, 'get_corrected_commands', side_effect=corrections)
    process = mocker.patch('subprocess.Popen')

    api.suggest('gti status', 'command not found')

    process.assert_not_called()


def test_suggest_requires_text():
    try:
        api.suggest(['gti', 'status'])
    except TypeError as error:
        assert str(error) == 'script must be a string'
    else:
        assert False, 'non-string script was accepted'


@pytest.mark.parametrize('function', [api.suggest, api.why])
def test_api_rejects_an_empty_script(function):
    with pytest.raises(ValueError, match='non-empty command'):
        function(' \t\n')


@pytest.mark.parametrize('function', [api.suggest, api.why])
def test_api_rejects_nul_bytes_in_a_script(function):
    with pytest.raises(ValueError, match='NUL bytes'):
        function('git\x00status')


def test_suggest_requires_text_output():
    try:
        api.suggest('gti status', b'command not found')
    except TypeError as error:
        assert str(error) == 'output must be a string or None'
    else:
        assert False, 'non-string output was accepted'


@pytest.mark.parametrize('function', [api.suggest, api.why])
def test_api_rejects_oversized_output(function):
    with pytest.raises(ValueError, match='8 MiB limit'):
        function('gti status', 'x' * (api.MAX_OUTPUT + 1))


def test_api_limits_utf8_bytes(monkeypatch):
    monkeypatch.setattr(api, 'MAX_OUTPUT', 1)
    with pytest.raises(ValueError, match='8 MiB limit'):
        api.suggest('gti status', u'\N{SNOWMAN}')


def test_suggest_keeps_action_details_labeled(mocker):
    correction = CorrectedCommand(
        'sudo rm -r cache', lambda *_: None, 1200, rule=Rule())
    mocker.patch.object(api, 'get_corrected_commands',
                        return_value=iter([correction]))

    explanation = api.suggest('rm -r cache', 'permission denied')
    labels = [item['label'] for item in explanation['suggestions'][0]
              ['explanation']]

    assert labels == ['rule', 'matched', 'read', 'side effect', 'runs as']


def test_suggest_marks_command_only_confidence(mocker):
    correction = CorrectedCommand('git status', None, 1200,
                                  rule=type('Rule', (), {
                                      'name': 'test_rule',
                                      'requires_output': False})())
    mocker.patch.object(api, 'get_corrected_commands',
                        return_value=iter([correction]))

    suggestion = api.suggest('gti status')['suggestions'][0]

    assert suggestion['confidence'] == {
        'level': 'medium',
        'basis': ['the rule matched the command or local context']}


def test_suggest_marks_explicitly_risky_corrections(mocker):
    correction = CorrectedCommand(
        'sudo rm -rf cache', None, 1200, rule=Rule())
    mocker.patch.object(api, 'get_corrected_commands',
                        return_value=iter([correction]))

    suggestion = api.suggest('rm cache', 'permission denied')['suggestions'][0]

    assert suggestion['risk'] == 'high'
    assert suggestion['risk_factors'] == [
        'privilege escalation', 'destructive command']


def test_why_returns_the_versioned_diagnosis_contract():
    assert api.why('python app.py',
                   "ModuleNotFoundError: No module named 'tomli'",
                   platform_name='posix') == {
        'schema': 1,
        'command': 'python app.py',
        'output_supplied': True,
        'decision': 'diagnose',
        'diagnoses': [{
            'kind': 'missing_python_module',
            'summary': "Python could not import module 'tomli'.",
            'evidence': ["No module named 'tomli'"],
            'next_steps': [{
                'command': 'python -m pip show tomli',
                'reason': 'check whether a distribution with this name is '
                          'installed',
                'risk': 'read-only'}]}]}


def test_why_can_describe_a_different_target_platform():
    result = api.why(
        'python server.py --port 5432',
        'OSError: [WinError 10048] Address already in use',
        platform_name='nt')

    assert result['diagnoses'][0]['next_steps'][0]['command'] == (
        'netstat -ano -p tcp | findstr ":5432"')
