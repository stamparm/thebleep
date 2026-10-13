# -*- encoding: utf-8 -*-

"""Asking something of your own choosing when `--why` has nothing to say.

`--why` recognises a small, deterministic set of failures and abstains on the
rest, because a plausible explanation is not proof. Some people would rather
have the plausible explanation, from a program they trust -- a local model, a
team script, `llm`, anything -- and this is the hook for it:

    why_command = 'ollama run llama3'

When the deterministic diagnosis abstains and that setting is on, the command
is run once, in the user's shell, with the failed command in
`THEBLEEP_FAILED_COMMAND`, its exit status in `THEBLEEP_FAILED_EXIT`, and
what it printed on standard input. Whatever comes back is printed under a
line saying where it came from. That is the whole contract.

What this does not do is as important. Nothing is bundled or recommended;
nothing is sent anywhere the user did not name; the structured API and the
MCP server never call it, because their promise is that the answer is
deterministic and this one is not. It runs only for the interactive `--why`,
only when the deterministic answer was silence, and only for the person who
wrote the setting.

"""

import os
import subprocess

from .conf import settings

COMMAND_ENV = 'THEBLEEP_FAILED_COMMAND'
EXIT_ENV = 'THEBLEEP_FAILED_EXIT'
MAX_INPUT = 256 * 1024
MAX_ANSWER = 64 * 1024


def configured():
    """The user's explainer command, or None."""
    value = settings.why_command
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def ask(script, output, exit_status=None, timeout=None):
    """Run the configured explainer once. Returns its answer, or None.

    :type script: str
    :type output: str | None
    :rtype: str | None

    """
    return _run(configured(), script, output, exit_status, timeout)


def suggester():
    """The user's `suggest_command`, or None."""
    value = settings.suggest_command
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def suggest(script, output, exit_status=None, timeout=None):
    """A command from `suggest_command` when no rule had one, or None.

    The same contract as `why_command`, asked for a command instead of an
    explanation: the first line it prints that is not a code fence, with any
    backticks round it taken off. It is offered as one row saying where it
    came from, is never run without the prompt (it has no confidence to
    pass `auto_run_confidence` with), and the API, the MCP server and the
    agent hooks never call it.

    """
    answer = _run(suggester(), script, output, exit_status, timeout)
    if answer is None:
        return None
    for line in answer.splitlines():
        line = line.strip()
        if not line or line.startswith('```'):
            continue
        line = line.strip('`').strip()
        if line.startswith('$ '):
            line = line[2:].strip()
        return line if line and line != script.strip() else None
    return None


def _run(command, script, output, exit_status=None, timeout=None):
    if command is None:
        return None
    if timeout is None:
        timeout = settings.why_timeout or 30

    environment = dict(os.environ)
    environment[COMMAND_ENV] = script
    environment[EXIT_ENV] = str(exit_status) if exit_status is not None \
        else ''
    fed = (output or u'')[:MAX_INPUT]

    from .shells import shell

    argv = shell.replay_argv(command) or ['/bin/sh', '-c', command]
    try:
        completed = subprocess.run(
            argv, input=fed.encode('utf-8', 'replace'),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=environment, timeout=timeout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if completed.returncode != 0:
        # A program that failed has not explained anything; what it said
        # about its own failure goes to the debug log, not the screen.
        from . import logs

        logs.debug(u'{} exited {}: {}'.format(
            command, completed.returncode,
            completed.stderr.decode('utf-8', 'replace')[:500].strip()))
        return None
    answer = completed.stdout.decode('utf-8', 'replace')[:MAX_ANSWER].strip()
    return answer or None


def heading():
    """`from ollama run llama3:` -- what the answer is introduced with."""
    return u'from {}, which is not a deterministic source:'.format(
        configured())
