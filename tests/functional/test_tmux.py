# -*- encoding: utf-8 -*-

import os
import shutil
import subprocess
import time

import pytest

from thebleep.output_readers import tmux


@pytest.mark.functional
def test_real_tmux_capture_does_not_replay_the_command(tmpdir, monkeypatch):
    if os.name == 'nt' or shutil.which('tmux') is None:
        pytest.skip('tmux is not available')

    socket = str(tmpdir.join('tmux.sock'))
    tmux_command = ['tmux', '-S', socket]
    script = "printf 'tmux capture works\\n'"
    monkeypatch.setenv('HOME', str(tmpdir))
    subprocess.check_call(tmux_command + [
        'new-session', '-d', '-s', 'capture', 'bash', '--noprofile', '--norc'])
    try:
        subprocess.check_call(tmux_command + [
            'send-keys', '-t', 'capture', "PS1='user$ '", 'Enter'])
        subprocess.check_call(tmux_command + [
            'send-keys', '-t', 'capture', script, 'Enter'])
        time.sleep(0.3)
        tmux_state = subprocess.check_output(
            tmux_command + ['display-message', '-p',
                            '#{socket_path},#{pid},#{window_index},#{pane_id}'],
            universal_newlines=True).strip()
        monkeypatch.setenv('TMUX', tmux_state)
        monkeypatch.setenv('TMUX_PANE', '%0')

        captured = tmux._capture()
        assert captured is not None, repr({
            'TMUX': os.environ.get('TMUX'),
            'TMUX_PANE': os.environ.get('TMUX_PANE')})
        assert tmux._output(script, captured) == 'tmux capture works', repr(captured)
    finally:
        subprocess.call(tmux_command + ['kill-server'])
