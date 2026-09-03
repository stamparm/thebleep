# -*- encoding: utf-8 -*-

"""Shared safe capture and prompt parsing for terminal panes."""

import os
import subprocess
import threading

from .. import const, logs
from ..utils import Tail, drain, without_control_sequences


TIMEOUT = 1.0
MAX_CAPTURE = const.LOG_SIZE_IN_BYTES
PROMPT_ENDS = '$#>%\u276f\u279c\u03bb\u2192\u00bb'


def capture(arguments, name):
    """Run a terminal's read-only capture command, with hard bounds."""
    try:
        process = subprocess.Popen(
            arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)
    except (OSError, ValueError) as error:
        logs.debug(u"{} capture could not start: {}".format(name, error))
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
    value = sink.value()
    if reader.is_alive() or process.returncode != 0 or sink.truncated:
        return None
    return value.decode('utf-8', errors='replace')


def _prompt():
    """A rendered prompt supplied by an integration, when available."""
    # Only a prompt an integration rendered: `PS1`, when exported, is the
    # unexpanded template (`\\u@\\h:\\w\\$`), which no captured line begins
    # with.
    prompt = os.environ.get('TB_PROMPT')
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
    """Whether `line` is the prompt that ended the failed command's output.

    The capture is taken while `bleep` itself is running, so the line after
    the output is not a bare prompt but the prompt with `bleep` typed on it,
    and a capture where the user had already typed the next command looks the
    same. Equality alone never ended the output in the real shape.

    """
    text = line.rstrip()
    ending = (prompt or command_prompt).rstrip()
    return text == ending or text.startswith(ending + ' ')


def output(script, capture_text):
    """Return output between the failed command and its next prompt."""
    prompt = _prompt()
    lines = without_control_sequences(capture_text).splitlines()
    for index in range(len(lines) - 1, -1, -1):
        command_prompt = _command_prompt(lines[index], script, prompt)
        if command_prompt is None:
            continue
        result = []
        for line in lines[index + 1:]:
            if _is_prompt_line(line, prompt, command_prompt):
                return '\n'.join(result).strip()
            result.append(line)
        return None
    return None
