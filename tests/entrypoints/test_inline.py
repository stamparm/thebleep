import os
from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize('command_text', ["echo 'unfinished", 'echo $(gti'])
def test_inline_abstains_on_incomplete_shell_syntax(mocker, capsys,
                                                    command_text):
    mocker.patch.object(type(inline.settings), 'init')
    corrections = mocker.patch.object(
        inline, 'get_corrected_commands', return_value=[])

    assert inline.inline_command(_args(command_text=command_text)) == 1
    assert capsys.readouterr().out == ''
    corrections.assert_not_called()


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


@pytest.mark.parametrize('line', ['reset; ssh user@web-server',
                                  'ssh user@web-server',
                                  'true && ssh user@mail'])
def test_a_line_is_not_rewritten_to_a_host_from_history(tmp_path, line):
    """The whole path, in a process of its own, with the history the shell
    hands over: `reset; ssh user@web-server` came back as `reset; ssh
    user@build-server` -- with nothing run, a different host each time the
    history moved. `--inline` is what every `--ambient` binding asks."""
    import subprocess
    import sys

    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    # The history rule reads the shell's history file, so the test brings
    # its own and a home of its own: never the real one.
    history = tmp_path / 'bash_history'
    history.write_text(u'\n'.join([
        'reset; ssh user@build-server', 'reset; ssh user@mail-server',
        'ssh user@build-server', 'true && ssh user@mail-server']) + u'\n')
    env = dict(os.environ, TB_SHELL='bash', PYTHONPATH=root,
               HOME=str(tmp_path), USERPROFILE=str(tmp_path),
               HISTFILE=str(history),
               XDG_CACHE_HOME=str(tmp_path / 'cache'),
               XDG_CONFIG_HOME=str(tmp_path / 'config'))
    env.pop('TB_HISTORY', None)
    done = subprocess.run(
        [sys.executable, '-m', 'thebleep', '--inline', '--command', line],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=60)
    assert done.stdout.decode().strip() == ''
