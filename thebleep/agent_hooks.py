# -*- encoding: utf-8 -*-

"""The Bleep underneath a coding agent.

Agents mistype commands the way people do, and pay more for it: a `gti status`
costs a turn, a model call, and whatever the agent decides the failure meant.
Claude Code and Cursor both run user-supplied hooks around the shell commands
their agents issue, with JSON on stdin and JSON on stdout. This module is
those hooks.

Two moments, both read-only, neither running the agent's command:

- **Before the command runs.** If a word that is about to be executed as a
  program is on nobody's `PATH` and a correction exists, the call is refused
  with the correction as the reason, and the agent re-issues it fixed. Only
  the *program* words are checked -- `gti` in `gti status`, `pytets` in
  `cd tests && pytets -q` -- and only when the line does nothing that could
  put a program on `PATH` first, such as `source venv/bin/activate` or
  `nvm use`. A word this cannot account for is left to run.

- **After it failed.** The failure text the agent would have read anyway is
  given to the same rules and the same `--why` fingerprints as an interactive
  correction, and the answer is attached as context beside the failed result:
  the suggested command, its confidence, and a deterministic diagnosis where
  there is one. Nothing is decided for the agent; it reads the note with the
  error.

`thebleep --hook claude-code` prints the settings to paste; `--as-hook` is
what those settings run. The protocol facts -- field names, where files go,
what a decision is called -- come from each tool's own hooks reference, and
the tests hold the payloads those references show.

"""

import json
import os
import sys

AGENTS = ('claude-code', 'cursor')

# What the before-hook does with a command whose program is misspelled:
# refuse it with the fix as the reason, hand the decision to the person, or
# let it run with the fix as a note. `THEBLEEP_HOOK_DECISION` picks.
DECISION_ENV = 'THEBLEEP_HOOK_DECISION'
DECISIONS = ('deny', 'ask', 'context')
DEFAULT_DECISION = 'deny'

# How much of an agent's failure output the rules are given, and how long the
# note back to the agent may be.
MAX_OUTPUT = 256 * 1024
MAX_NOTE = 1200

# Programs that change what a later word in the same line resolves to. A line
# with one of these in it is not checked: `source .venv/bin/activate && pytest`
# is correct, and `pytest` is not on PATH until the first half has run.
CHANGES_PATH = frozenset((
    'source', '.', 'eval', 'export', 'nvm', 'conda', 'pyenv', 'rbenv', 'nodenv',
    'asdf', 'mise', 'direnv', 'module', 'sdk', 'volta', 'fnm', 'rustup',
    'uv', 'uvx', 'npx', 'pipx', 'poetry', 'pnpm', 'yarn', 'bun', 'bunx',
    'docker', 'podman', 'ssh', 'sudo', 'doas', 'env', 'command', 'exec',
    'nix', 'nix-shell', 'devbox', 'flox', 'chroot', 'su', 'xargs',
    'make', 'just', 'task',
))

# Keywords after which the command is the *next* word: `if gti status`,
# `time pytets`, `! grpe`.
BEFORE_THE_COMMAND = frozenset((
    'if', 'then', 'else', 'elif', 'do', 'while', 'until', '!', 'time', '{',
    'coproc',
))

# Words a POSIX shell resolves without a PATH lookup. `replay` keeps the ones
# with effects; these are the rest that turn up at the front of a command.
SHELL_WORDS = frozenset((
    'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'until', 'do', 'done',
    'case', 'esac', 'in', 'function', 'select', 'time', 'coproc', '{', '}',
    '!', '[', '[[', 'test', 'true', 'false', ':', 'echo', 'printf', 'read',
    'cd', 'pwd', 'pushd', 'popd', 'dirs', 'set', 'unset', 'shift', 'local',
    'declare', 'typeset', 'readonly', 'let', 'return', 'exit', 'break',
    'continue', 'trap', 'wait', 'jobs', 'fg', 'bg', 'kill', 'type', 'hash',
    'alias', 'unalias', 'builtin', 'enable', 'ulimit', 'umask', 'getopts',
    'times', 'help', 'mapfile', 'readarray', 'compgen', 'complete', 'shopt',
    'caller', 'disown', 'suspend', 'logout', 'history', 'fc', 'bind',
))


def _program_words(script):
    """The words `script` would run as programs, or None if unsure.

    None -- rather than an empty list -- when the line is incomplete, does
    something that could change what a word resolves to, or has a shape this
    does not follow. The hook then says nothing.

    """
    from .command_model import parse

    model = parse(script, 'posix')
    if not model.complete or not model.segments:
        return None

    words = []
    for segment in model.segments:
        tokens = segment.tokens
        if not tokens:
            continue
        if tokens[0].kind != 'word':
            # `$(which x) status`, `"$cmd" arg`: the program is whatever the
            # substitution or quoting produces, and that is not known here.
            return None
        found = [token.text for token in tokens if token.kind == 'word']
        while found and found[0] in BEFORE_THE_COMMAND:
            found.pop(0)
        if not found:
            continue
        first = found[0]
        if '=' in first and not first.startswith('='):
            # `FOO=bar cmd`: the assignment is not the program and the
            # program may depend on it. Leave the line alone.
            return None
        if first in CHANGES_PATH:
            return None
        if first in SHELL_WORDS:
            continue
        if '/' in first or '\\' in first or first.startswith(('$', '~')):
            continue
        if any(character in first for character in '`"\'{}()*?'):
            return None
        words.append(first)
    return words


def _missing_programs(words):
    from .utils import which

    return [word for word in words if which(word) is None]


def _suggestion_for(script, output=None, resolving=None):
    """The first structured suggestion for `script`, or None.

    With `resolving`, only a suggestion in which every program word is on
    PATH counts: the point of the before-hook is the misspelled program, and
    a rule that fixed something else while leaving it in place -- `ls -lah |
    grpe foo` for `ls | grpe foo` -- has not answered the question.

    """
    from . import api

    try:
        result = api.suggest(script, output)
    except (TypeError, ValueError):
        return None
    if result.get('decision') != 'suggest':
        return None
    for suggestion in result.get('suggestions') or ():
        if suggestion['command'] == script:
            continue
        if resolving:
            words = _program_words(suggestion['command'])
            if words is None or _missing_programs(words):
                continue
        return suggestion
    return None


def _shell_said_not_found(missing):
    """What the shell prints for `missing`: the message a rule reads.

    bash's wording, for one program that was not found. This is not a guess
    about a fixture: it is the message the agent's shell would print in a
    moment, written down before the moment so that the rule that reads it can
    answer first. `bash -c 'gti status'` prints exactly this line.

    """
    return u'bash: line 1: {}: command not found'.format(missing)


def check_before(script):
    """The correction for a command about to run, or None to say nothing.

    :rtype: dict | None -- `missing`, `command`, `confidence`, `reason`.

    """
    if not isinstance(script, str) or not script.strip():
        return None
    words = _program_words(script)
    if not words:
        return None
    missing = _missing_programs(words)
    if len(missing) != 1:
        # None: nothing to say. Several: `no_command` can fix them together,
        # but two wrong program names in one agent line is rare enough that a
        # confident answer is unlikely; let the shell report both.
        return None

    suggestion = _suggestion_for(script, _shell_said_not_found(missing[0]),
                                 resolving=True)
    if suggestion is None or suggestion['risk'] != 'low':
        return None
    score = suggestion['confidence']['score']
    return {
        'missing': missing[0],
        'command': suggestion['command'],
        'confidence': score,
        'reason': (u'`{}` is not a program on PATH. The Bleep suggests: '
                   u'`{}`{}').format(
            missing[0], suggestion['command'],
            u' ({}% confidence)'.format(int(round(score * 100)))
            if score is not None else u''),
    }


def _output_from_error(error):
    """The command's output out of Claude Code's `error` string.

    `Exit code N` on the first line, then the output, stdout and stderr
    interleaved. A payload without that line is a shell that failed to start,
    and there is no output to read then.

    """
    if not isinstance(error, str) or not error:
        return None
    first, _, rest = error.partition('\n')
    if not first.startswith('Exit code '):
        return None
    return rest[:MAX_OUTPUT]


def note_after(script, output, platform_name=None):
    """What to tell an agent whose command has just failed, or None."""
    if not isinstance(script, str) or not script.strip():
        return None
    if output is None:
        return None
    lines = []
    suggestion = _suggestion_for(script, output)
    if suggestion is not None:
        score = suggestion['confidence']['score']
        basis = (suggestion['confidence'].get('basis') or [''])[0]
        lines.append(u'The Bleep suggests: `{}`{}{}'.format(
            suggestion['command'],
            u' ({}% confidence'.format(int(round(score * 100)))
            if score is not None else u'',
            (u', {})'.format(basis) if basis else u')')
            if score is not None else u''))
        if suggestion['risk'] != 'low':
            lines.append(u'Risk markers: {}.'.format(
                ', '.join(suggestion['risk_factors'])))

    from . import api

    try:
        diagnosis = api.why(script, output, platform_name)
    except (TypeError, ValueError):
        diagnosis = None
    for found in (diagnosis or {}).get('diagnoses') or ():
        lines.append(u'Diagnosis: {}'.format(found['summary']))
        for step in found.get('next_steps') or ():
            lines.append(u'  next: `{}` ({}, {})'.format(
                step['command'], step['reason'], step['risk']))

    if not lines:
        return None
    note = u'\n'.join(lines)
    if len(note) > MAX_NOTE:
        note = note[:MAX_NOTE - 1] + u'…'
    return note


def decision():
    chosen = os.environ.get(DECISION_ENV, DEFAULT_DECISION).strip().lower()
    return chosen if chosen in DECISIONS else DEFAULT_DECISION


def _claude_code(payload):
    event = payload.get('hook_event_name')
    tool = payload.get('tool_name')
    if tool not in ('Bash', 'PowerShell'):
        return None
    tool_input = payload.get('tool_input') or {}
    script = tool_input.get('command')

    if event == 'PreToolUse':
        found = check_before(script)
        if found is None:
            return None
        chosen = decision()
        output = {'hookEventName': 'PreToolUse'}
        if chosen == 'context':
            output['additionalContext'] = found['reason']
        else:
            output['permissionDecision'] = chosen
            output['permissionDecisionReason'] = found['reason']
        return {'hookSpecificOutput': output}

    if event == 'PostToolUseFailure':
        if payload.get('is_interrupt'):
            return None
        note = note_after(script, _output_from_error(payload.get('error')),
                          'nt' if tool == 'PowerShell' else 'posix')
        if note is None:
            return None
        return {'hookSpecificOutput': {'hookEventName': 'PostToolUseFailure',
                                       'additionalContext': note}}
    return None


def _cursor(payload):
    if payload.get('hook_event_name') != 'beforeShellExecution':
        return None
    found = check_before(payload.get('command'))
    if found is None:
        return None
    chosen = decision()
    if chosen == 'context':
        return {'permission': 'allow', 'agent_message': found['reason']}
    return {'permission': chosen,
            'user_message': u'`{}` looks like `{}`'.format(
                found['missing'], found['command']),
            'agent_message': found['reason']}


HANDLERS = {'claude-code': _claude_code, 'cursor': _cursor}


def handle(agent, payload):
    """The JSON to answer `payload` with, or None for no opinion."""
    handler = HANDLERS.get(agent)
    if handler is None or not isinstance(payload, dict):
        return None
    return handler(payload)


def run(agent, stdin=None, stdout=None):
    """Read one hook payload, write one answer. Never fails the agent.

    A hook that crashes or exits 2 blocks the agent's command, and no bug in a
    typo corrector should do that: any error is a debug line and exit 0 with
    nothing on stdout, which every host reads as "no decision".

    """
    from . import logs

    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if agent not in AGENTS:
        logs.failed(u'Unknown agent {!r}; one of {}'.format(
            agent, ', '.join(AGENTS)))
        return 2
    try:
        payload = json.loads(stdin.read(4 * 1024 * 1024) or '{}')
        answer = handle(agent, payload)
    except Exception as error:
        logs.debug(u'Hook said nothing: {!r}'.format(error))
        return 0
    if answer is not None:
        stdout.write(json.dumps(answer))
        stdout.write('\n')
    return 0


def _program():
    """How the hook should invoke The Bleep, as one shell string."""
    from .invocation import command

    return command()


def config(agent):
    """The configuration to paste, and where, for `agent`.

    :rtype: (str, str) -- the JSON, and the instructions for it.

    """
    run_as = u'{} --as-hook {}'.format(_program(), agent)
    if agent == 'claude-code':
        settings = {'hooks': {
            'PreToolUse': [{'matcher': 'Bash|PowerShell', 'hooks': [
                {'type': 'command', 'command': run_as, 'timeout': 10}]}],
            'PostToolUseFailure': [{'matcher': 'Bash|PowerShell', 'hooks': [
                {'type': 'command', 'command': run_as, 'timeout': 10}]}],
        }}
        where = (
            u'Merge this into ~/.claude/settings.json, or into '
            u'.claude/settings.json in a project.\n'
            u'Before a Bash command runs, a misspelled program is refused '
            u'with the correction as the reason;\n'
            u'after one fails, the suggestion and diagnosis are attached to '
            u'the result.\n'
            u'{}=ask asks you instead of refusing; =context lets it run '
            u'and only adds the note.'.format(DECISION_ENV))
    elif agent == 'cursor':
        settings = {'version': 1, 'hooks': {
            'beforeShellExecution': [{'command': run_as, 'timeout': 10}]}}
        where = (
            u'Save this as ~/.cursor/hooks.json, or as .cursor/hooks.json in '
            u'a project.\n'
            u'Before a shell command runs, a misspelled program is refused '
            u'with the correction as the message.\n'
            u'{}=ask asks you instead of refusing; =context lets it run '
            u'and only passes the note.'.format(DECISION_ENV))
    else:
        raise ValueError(agent)
    return json.dumps(settings, indent=2), where


def print_config(agent):
    from . import logs

    if agent not in AGENTS:
        logs.failed(u'Unknown agent {!r}; one of {}'.format(
            agent, ', '.join(AGENTS)))
        return 2
    text, where = config(agent)
    sys.stdout.write(text + '\n')
    sys.stderr.write(where + '\n')
    return 0
