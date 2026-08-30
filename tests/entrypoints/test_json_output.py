import json

import thebleep.entrypoints.json_output as json_output_module
from thebleep.entrypoints.json_output import json_output


def _args(command, stderr=None, cwd=None, command_text=None):
    class Arguments(object):
        pass

    args = Arguments()
    args.command = command
    args.command_text = command_text
    args.stderr = stderr
    args.cwd = cwd
    args.why = False
    args.yes = args.debug = args.repeat = args.edit = args.explain = False
    return args


def _no_settings(mocker):
    mocker.patch.object(type(json_output_module.settings), 'init')


def test_json_output_uses_captured_output_and_restores_cwd(
        tmpdir, mocker, capsys):
    output = tmpdir.join('error.txt')
    output.write('git: unknown command')
    _no_settings(mocker)
    suggest = mocker.patch(
        'thebleep.entrypoints.json_output.api.suggest',
        return_value={'suggestions': []})

    assert json_output(_args(['gti', 'status'], str(output), str(tmpdir))) == 0

    suggest.assert_called_once_with('gti status', 'git: unknown command')
    assert json.loads(capsys.readouterr().out) == {'suggestions': []}


def test_json_output_preserves_an_exact_command(mocker, capsys):
    _no_settings(mocker)
    suggest = mocker.patch(
        'thebleep.entrypoints.json_output.api.suggest',
        return_value={'suggestions': []})
    args = _args([], command_text="cd 'a b' && gti status")

    assert json_output(args) == 0
    suggest.assert_called_once_with("cd 'a b' && gti status", None)
    assert json.loads(capsys.readouterr().out) == {'suggestions': []}


def test_json_output_can_diagnose_captured_output(mocker, capsys):
    _no_settings(mocker)
    why = mocker.patch(
        'thebleep.entrypoints.json_output.api.why',
        return_value={'diagnoses': []})
    args = _args([], command_text='python app.py')
    args.why = True

    assert json_output(args) == 0
    why.assert_called_once_with('python app.py', None, None)
    assert json.loads(capsys.readouterr().out) == {'diagnoses': []}


def test_json_output_passes_target_platform(mocker, capsys):
    _no_settings(mocker)
    why = mocker.patch(
        'thebleep.entrypoints.json_output.api.why',
        return_value={'diagnoses': []})
    args = _args([], command_text='python app.py')
    args.why = True
    args.platform_name = 'nt'

    assert json_output(args) == 0
    why.assert_called_once_with('python app.py', None, 'nt')
    assert json.loads(capsys.readouterr().out) == {'diagnoses': []}


def test_json_output_rejects_both_command_forms(mocker, capsys):
    _no_settings(mocker)
    assert json_output(_args(['gti'], command_text='git status')) == 2
    assert 'cannot be combined' in capsys.readouterr().err


def test_json_output_rejects_an_empty_command(mocker, capsys):
    _no_settings(mocker)
    assert json_output(_args([], command_text='  ')) == 2
    assert 'non-empty command' in capsys.readouterr().err


def test_json_output_requires_a_command(mocker, capsys):
    _no_settings(mocker)
    assert json_output(_args([])) == 2
    assert '--json needs a command' in capsys.readouterr().err


def test_json_output_reports_a_missing_output_file(tmpdir, mocker, capsys):
    _no_settings(mocker)
    assert json_output(_args(['gti'], str(tmpdir.join('missing')))) == 2
    assert 'Could not read' in capsys.readouterr().err


def test_json_output_reads_output_from_stdin(mocker, capsys, monkeypatch):
    _no_settings(mocker)
    monkeypatch.setattr(json_output_module.sys, 'stdin', type(
        'Input', (), {'read': lambda self, size: 'gti: command not found'})())
    suggest = mocker.patch(
        'thebleep.entrypoints.json_output.api.suggest',
        return_value={'suggestions': []})

    assert json_output(_args(['gti'], '-')) == 0

    suggest.assert_called_once_with('gti', 'gti: command not found')
    assert json.loads(capsys.readouterr().out) == {'suggestions': []}


def test_json_output_rejects_oversized_output(tmpdir, mocker, capsys):
    _no_settings(mocker)
    output = tmpdir.join('too-large')
    output.write('x' * (json_output_module.MAX_OUTPUT + 1))

    assert json_output(_args(['gti'], str(output))) == 2
    assert 'limit' in capsys.readouterr().err


def test_read_output_limits_raw_utf8_bytes(tmpdir, mocker, capsys):
    _no_settings(mocker)
    output = tmpdir.join('too-large-unicode')
    output.write_binary(u'\N{SNOWMAN}'.encode('utf-8'))
    mocker.patch.object(json_output_module, 'MAX_OUTPUT', 1)

    assert json_output(_args(['gti'], str(output))) == 2
    assert 'limit' in capsys.readouterr().err
