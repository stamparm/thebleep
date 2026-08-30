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
        'schema': 2,
        'command': 'gti status',
        'structure': {
            'shell': 'posix',
            'complete': True,
            'segments': [{
                'start': 0,
                'end': 10,
                'separator': None,
                'command': 'gti',
                'tokens': [
                    {'text': 'gti', 'start': 0, 'end': 3, 'kind': 'word'},
                    {'text': 'status', 'start': 4, 'end': 10,
                     'kind': 'word'}]}]},
        'output_supplied': True,
        'decision': 'suggest',
        'suggestions': [{
            'command': 'git status',
            'edits': [{'start': 0, 'end': 3, 'source': 'gti',
                       'replacement': 'git'}],
            'rule': 'test_rule',
            'priority': 1200,
            'confidence': {
                'score': 0.95,
                'level': 'high',
                'basis': ['the rule matched captured command output']},
            'side_effect': False,
            'risk': 'low',
            'risk_factors': [],
            'requires_output': True,
            'evidence': [
                'a condition this rule works out for itself',
                'what your command printed'],
            'evidence_details': [
                {'kind': 'source',
                 'text': 'test_rule (from somewhere unrecorded)'},
                {'kind': 'match',
                 'text': 'a condition this rule works out for itself'},
                {'kind': 'context', 'text': 'what your command printed'}],
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


@pytest.mark.parametrize('script', ["echo 'unfinished", 'echo $(gti status'])
def test_suggest_abstains_on_incomplete_shell_syntax(mocker, script):
    corrections = mocker.patch.object(
        api, 'get_corrected_commands', return_value=iter([]))

    result = api.suggest(script)

    assert result['structure']['complete'] is False
    assert result['decision'] == 'abstain'
    assert result['suggestions'] == []
    corrections.assert_not_called()


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
        'score': 0.75,
        'basis': ['the rule matched the command or local context']}


def test_suggest_exposes_source_edits_for_compound_commands(mocker):
    correction = CorrectedCommand(
        'cd foo && git status | grep main', None, 1200, rule=Rule())
    mocker.patch.object(api, 'get_corrected_commands',
                        return_value=iter([correction]))

    result = api.suggest('cd foo && gti status | grep main', 'error')

    assert result['suggestions'][0]['edits'] == [{
        'start': 10,
        'end': 13,
        'source': 'gti',
        'replacement': 'git',
    }]


def test_large_suggestion_uses_one_bounded_source_edit():
    original = 'x' * (api.MAX_EDIT_DIFF + 1)
    replacement = 'y' * (api.MAX_EDIT_DIFF + 1)

    assert api._edits(original, replacement) == [{
        'start': 0,
        'end': len(original),
        'source': original,
        'replacement': replacement,
    }]


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
        'schema': 2,
        'command': 'python app.py',
        'structure': {
            'shell': 'posix',
            'complete': True,
            'segments': [{
                'start': 0,
                'end': 13,
                'separator': None,
                'command': 'python',
                'tokens': [
                    {'text': 'python', 'start': 0, 'end': 6, 'kind': 'word'},
                    {'text': 'app.py', 'start': 7, 'end': 13,
                     'kind': 'word'}]}]},
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
