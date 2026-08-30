# -*- encoding: utf-8 -*-

import pytest

from thebleep.output_readers import pane, tmux


def test_a_command_must_follow_a_prompt():
    capture = 'user$ echo git status\ngit status\nuser$ '

    assert tmux._output('git status', capture) is None


@pytest.mark.parametrize('script, capture, expected', [
    ('gti status', 'user$ gti status\ngti: command not found\nuser$ ',
     'gti: command not found'),
    ('true', 'user$ true\nuser$ ', ''),
])
def test_output_is_taken_between_command_and_next_prompt(
        script, capture, expected, monkeypatch):
    monkeypatch.setenv('TB_PROMPT', 'user$ ')

    assert tmux._output(script, capture) == expected


def test_unfinished_pane_is_not_an_answer(monkeypatch):
    monkeypatch.setenv('TB_PROMPT', 'user$ ')

    assert tmux._output('gti status', 'user$ gti status\nerror') is None


def test_prompt_like_output_does_not_end_the_capture(monkeypatch):
    monkeypatch.setenv('TB_PROMPT', 'user$ ')

    assert tmux._output(
        'gti status', 'user$ gti status\nerror$\nmore\nuser$ '
    ) == 'error$\nmore'


def test_capture_is_bounded_and_uses_the_current_pane(mocker, monkeypatch):
    monkeypatch.setenv('TMUX', 'socket,123,0')
    monkeypatch.setenv('TMUX_PANE', '%7')
    monkeypatch.setattr(tmux, 'which', lambda name: '/usr/bin/tmux')
    process = mocker.MagicMock(returncode=0)
    process.stdout.read.side_effect = [b'user$ gti status\nerror\nuser$ ', b'']
    mocker.patch.object(pane.subprocess, 'Popen', return_value=process)

    tmux._capture()

    pane.subprocess.Popen.assert_called_once_with(
        ['/usr/bin/tmux', '-S', 'socket', 'capture-pane', '-p', '-J',
         '-t', '%7'],
        stdin=pane.subprocess.DEVNULL, stdout=pane.subprocess.PIPE,
        stderr=pane.subprocess.DEVNULL)
