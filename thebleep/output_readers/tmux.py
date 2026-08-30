# -*- encoding: utf-8 -*-

"""Read the current tmux pane without running the failed command again."""

import os
import subprocess
import threading

from .. import const, logs
from ..utils import Tail, drain, without_control_sequences, which


TIMEOUT = 1.0
MAX_CAPTURE = const.LOG_SIZE_IN_BYTES
PROMPT_ENDS = '$#>%\u276f\u279c\u03bb\u2192\u00bb'


def is_available():
    """Whether this process is inside a tmux pane we can inspect."""
    return bool(os.environ.get('TMUX') and os.environ.get('TMUX_PANE')
                and which('tmux'))


def _capture():
    executable = which('tmux')
    tmux_state = os.environ.get('TMUX', '')
    if not tmux_state:
        return None
    socket = tmux_state.split(',', 1)[0]
    pane = os.environ.get('TMUX_PANE')
    if not executable or not socket or not pane:
        return None

    try:
        process = subprocess.Popen(
            [executable, '-S', socket, 'capture-pane', '-p', '-J',
             '-t', pane],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except (OSError, ValueError) as error:
        logs.debug(u"tmux capture could not start: {}".format(error))
        return None

    sink = Tail(MAX_CAPTURE)
    reader = threading.Thread(target=drain, args=(process.stdout, sink))
    reader.daemon = True
    reader.start()
    try:
        process.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            pass
        reader.join(1)
        return None

    reader.join(1)
    if process.returncode != 0 or sink.truncated:
        return None
    return sink.value().decode('utf-8', errors='replace')


def _prompt():
    """A rendered prompt supplied by an integration, when available."""
    prompt = os.environ.get('TB_PROMPT') or os.environ.get('PS1')
    if not prompt:
        return None
    prompt = prompt.replace(const.USER_COMMAND_MARK, '')
    prompt = prompt.replace('\b', '')
    if prompt.startswith('%{') and prompt.endswith('%}'):
        prompt = prompt[2:-2]
    return without_control_sequences(prompt)


def _command_prompt(line, script, prompt):
    text = line.rstrip()
    command = script.strip()
    if prompt and text.startswith(prompt):
        return prompt if text[len(prompt):].lstrip() == command else None

    position = text.find(command)
    if position == -1:
        return None
    prefix = text[:position].rstrip()
    return prefix if prefix and prefix[-1] in PROMPT_ENDS else None


def _is_prompt_line(line, prompt, command_prompt):
    text = line.rstrip()
    if prompt:
        return text == prompt.rstrip()
    return text == command_prompt.rstrip()


def _output(script, capture):
    prompt = _prompt()
    lines = without_control_sequences(capture).splitlines()
    for index in range(len(lines) - 1, -1, -1):
        command_prompt = _command_prompt(lines[index], script, prompt)
        if command_prompt is None:
            continue
        output = []
        for line in lines[index + 1:]:
            if _is_prompt_line(line, prompt, command_prompt):
                return '\n'.join(output).strip()
            output.append(line)
        return None
    return None


def get_output(script, expanded):
    """Return the current pane's output, or ``None`` when boundaries are weak."""
    capture = _capture()
    return _output(script, capture) if capture is not None else None
