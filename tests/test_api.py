from thebleep import api
from thebleep.types import CorrectedCommand


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
            'side_effect': False,
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


def test_suggest_requires_text():
    try:
        api.suggest(['gti', 'status'])
    except TypeError as error:
        assert str(error) == 'script must be a string'
    else:
        assert False, 'non-string script was accepted'


def test_suggest_requires_text_output():
    try:
        api.suggest('gti status', b'command not found')
    except TypeError as error:
        assert str(error) == 'output must be a string or None'
    else:
        assert False, 'non-string output was accepted'


def test_suggest_keeps_action_details_labeled(mocker):
    correction = CorrectedCommand(
        'sudo rm -r cache', lambda *_: None, 1200, rule=Rule())
    mocker.patch.object(api, 'get_corrected_commands',
                        return_value=iter([correction]))

    explanation = api.suggest('rm -r cache', 'permission denied')
    labels = [item['label'] for item in explanation['suggestions'][0]
              ['explanation']]

    assert labels == ['rule', 'matched', 'read', 'side effect', 'runs as']


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
