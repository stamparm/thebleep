# -*- coding: utf-8 -*-

import pytest

from thebleep.output_readers import kitty, pane, wezterm, zellij


@pytest.mark.parametrize('module, variable, value, expected', [
    (wezterm, 'WEZTERM_PANE', '7',
     ['wezterm', 'cli', 'get-text', '--pane-id', '7',
      '--start-line=-1000000']),
    (kitty, 'KITTY_WINDOW_ID', '7',
     ['kitten', '@', 'get-text', '--match', 'id:7', '--extent', 'all']),
])
def test_native_capture_targets_the_current_pane(
        module, variable, value, expected, monkeypatch, mocker):
    monkeypatch.setenv(variable, value)
    monkeypatch.setattr(module, 'which', lambda name: '/tools/{}'.format(name))
    capture = mocker.patch.object(pane, 'capture', return_value='screen')

    assert module.is_available()
    assert module._capture() == 'screen'
    capture.assert_called_once_with(
        ['/tools/{}'.format(expected[0])] + expected[1:], module.__name__.split('.')[-1])


def test_zellij_dumps_the_focused_pane_to_a_file(monkeypatch, mocker):
    """`zellij action dump-screen <PATH> [--full]`: a path, no pane flag,
    nothing on stdout. The old `--pane-id` form was rejected and the backend
    never answered."""
    monkeypatch.setenv('ZELLIJ_PANE_ID', 'terminal_7')
    monkeypatch.setattr(zellij, 'which', lambda name: '/tools/' + name)

    def dump(arguments, name):
        assert arguments[:3] == ['/tools/zellij', 'action', 'dump-screen']
        assert arguments[4] == '--full'
        with open(arguments[3], 'w') as handle:
            handle.write('screen')
        return ''

    mocker.patch.object(pane, 'capture', side_effect=dump)
    assert zellij.is_available()
    assert zellij._capture() == 'screen'


def test_kitty_rejects_non_numeric_window_ids(monkeypatch):
    monkeypatch.setenv('KITTY_WINDOW_ID', 'current')

    assert not kitty.is_available()


def test_capture_rejects_a_failed_helper(mocker):
    process = mocker.MagicMock(returncode=1)
    process.stdout.read.side_effect = [b'partial output', b'']
    mocker.patch.object(pane.subprocess, 'Popen', return_value=process)

    assert pane.capture(['zellij'], 'zellij') is None


def test_capture_rejects_a_helper_that_does_not_finish(mocker):
    process = mocker.MagicMock(returncode=None)
    process.stdout.read.side_effect = [b'', b'']
    process.wait.side_effect = pane.subprocess.TimeoutExpired('wezterm', 1)
    mocker.patch.object(pane.subprocess, 'Popen', return_value=process)

    assert pane.capture(['wezterm'], 'wezterm') is None
    process.kill.assert_called_once_with()


def test_capture_rejects_an_oversized_answer(mocker, monkeypatch):
    monkeypatch.setattr(pane, 'MAX_CAPTURE', 4)
    process = mocker.MagicMock(returncode=0)
    process.stdout.read.side_effect = [b'12345', b'']
    mocker.patch.object(pane.subprocess, 'Popen', return_value=process)

    assert pane.capture(['kitten'], 'kitty') is None


@pytest.mark.parametrize('module, variable', [
    (zellij, 'ZELLIJ_PANE_ID'),
    (wezterm, 'WEZTERM_PANE'),
    (kitty, 'KITTY_WINDOW_ID'),
])
def test_native_capture_uses_the_same_prompt_boundaries(
        module, variable, monkeypatch, mocker):
    monkeypatch.setenv(variable, '7' if module is not zellij else 'terminal_7')
    monkeypatch.setenv('TB_PROMPT', 'user$ ')
    monkeypatch.setattr(module, 'which', lambda name: '/tools/{}'.format(name))
    text = 'user$ gti status\ngti: not found\nuser$ '

    def capture(arguments, name):
        if module is zellij:
            with open(arguments[3], 'w') as handle:
                handle.write(text)
            return ''
        return text

    mocker.patch.object(pane, 'capture', side_effect=capture)

    assert module.get_output('gti status', 'gti status') == 'gti: not found'


def test_the_prompt_that_ends_the_output_has_bleep_typed_on_it(monkeypatch):
    """The capture is taken while `bleep` runs, so the line after the output is
    the prompt with `bleep` on it, not a bare prompt; equality never ended
    the output in the real shape."""
    monkeypatch.setenv('TB_PROMPT', 'user$ ')
    text = 'user$ gti status\ngti: not found\nuser$ bleep\n'
    assert pane.output('gti status', text) == 'gti: not found'
    monkeypatch.delenv('TB_PROMPT')
    assert pane.output('gti status', text) == 'gti: not found'


def test_an_exported_ps1_template_is_not_a_prompt(monkeypatch):
    monkeypatch.delenv('TB_PROMPT', raising=False)
    monkeypatch.setenv('PS1', '\\u@\\h:\\w\\$ ')
    assert pane._prompt() is None
