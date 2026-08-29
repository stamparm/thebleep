from types import SimpleNamespace

from thebleep import types
from thebleep.entrypoints import inline
from thebleep.shells import Generic


def _args(command=None, command_text=None):
    return SimpleNamespace(command=command or [], command_text=command_text)


def test_inline_uses_the_command_without_replaying_it(mocker, capsys):
    mocker.patch.object(type(inline.settings), 'init')
    corrected = SimpleNamespace(script='git status')
    seen = []

    def corrections(command):
        seen.append(command)
        return [corrected]

    mocker.patch.object(inline, 'get_corrected_commands', side_effect=corrections)
    from_raw_script = mocker.patch.object(types.Command, 'from_raw_script')

    assert inline.inline_command(_args(['gti', 'status'])) == 0

    assert capsys.readouterr().out == 'git status\n'
    assert seen == [types.Command('gti status', None)]
    assert not from_raw_script.called


def test_inline_returns_one_when_it_has_no_correction(mocker, capsys):
    mocker.patch.object(type(inline.settings), 'init')
    mocker.patch.object(inline, 'get_corrected_commands', return_value=[])

    assert inline.inline_command(_args(command_text='gti status')) == 1
    assert capsys.readouterr().out == ''


def test_inline_rejects_ambiguous_and_empty_commands(mocker, capsys):
    mocker.patch.object(type(inline.settings), 'init')

    assert inline.inline_command(_args(['gti'], 'git status')) == 2
    assert 'cannot be combined' in capsys.readouterr().err

    assert inline.inline_command(_args(command_text='  ')) == 2
    assert 'non-empty command' in capsys.readouterr().err


def test_print_binding_delegates_to_the_current_shell(mocker, capsys):
    mocker.patch.object(type(inline.settings), 'init')
    mocker.patch.object(inline.shell, 'inline_binding', return_value='binding\n')

    assert inline.print_binding(_args()) == 0
    assert capsys.readouterr().out == 'binding\n'


def test_print_binding_reports_unsupported_shell(mocker, capsys):
    mocker.patch.object(type(inline.settings), 'init')
    mocker.patch.object(inline, 'shell', Generic())

    assert inline.print_binding(_args()) == 2
    assert 'does not support' in capsys.readouterr().err
