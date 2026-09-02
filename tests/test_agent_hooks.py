# -*- encoding: utf-8 -*-

"""The hooks a coding agent runs around its shell commands.

The payloads here are the shapes each tool's hooks reference documents:
Claude Code's `PreToolUse` and `PostToolUseFailure` with `tool_name`,
`tool_input.command`, `error` and `is_interrupt`; Cursor's
`beforeShellExecution` with `command` and `cwd`.

"""

import io
import json

import pytest

from thebleep import agent_hooks


@pytest.fixture(autouse=True)
def a_machine_with_git_and_grep(mocker):
    """`which` answers for a fixed PATH, so the answers do not depend on the
    machine running the suite."""
    installed = {'git', 'grep', 'ls', 'pytest', 'python3', 'cat'}
    mocker.patch('thebleep.utils.which',
                 side_effect=lambda name: '/usr/bin/' + name
                 if name in installed else None)
    mocker.patch('thebleep.utils.get_all_executables',
                 return_value=sorted(installed))


@pytest.fixture(autouse=True)
def default_decision(os_environ):
    os_environ.pop(agent_hooks.DECISION_ENV, None)


class TestProgramWords(object):
    @pytest.mark.parametrize('script, expected', [
        ('gti status', ['gti']),
        ('cd /tmp && pytets -q', ['pytets']),
        ('ls | grpe foo', ['ls', 'grpe']),
        ('echo hi', []),
        ('./run.sh --flag', []),
        ('/usr/bin/env python3', []),
        ('if true; then ls; fi', ['ls']),
        ('if gti diff --quiet; then echo clean; fi', ['gti']),
        ('time pytets -q', ['pytets']),
    ])
    def test_the_words_that_run_as_programs(self, script, expected):
        assert agent_hooks._program_words(script) == expected

    @pytest.mark.parametrize('script', [
        'source .venv/bin/activate && pytets',
        '. ./env.sh; pytets',
        'nvm use 20 && npm test',
        'export PATH=/opt/bin:$PATH; tool',
        'FOO=1 gti status',
        'npx pretier --check .',
        'docker run --rm img gti',
        'sudo apt-get install',
        'make tset',
        'echo "unterminated',
        '$(which gti) status',
    ])
    def test_a_line_that_cannot_be_judged_is_left_alone(self, script):
        assert agent_hooks._program_words(script) is None


class TestCheckBefore(object):
    def test_a_misspelled_program_gets_its_correction(self):
        found = agent_hooks.check_before('gti status')
        assert found['missing'] == 'gti'
        assert found['command'] == 'git status'
        assert '`gti` is not a program on PATH' in found['reason']
        assert '`git status`' in found['reason']

    def test_the_fix_has_to_fix_the_program(self):
        """A rule that changed something else and left `grpe` in place has not
        answered; the one that fixed the program is the one wanted."""
        found = agent_hooks.check_before('ls | grpe foo')
        assert found['command'] == 'ls | grep foo'

    def test_after_a_cd(self):
        assert agent_hooks.check_before('cd /tmp && pytets -q')['command'] \
            == 'cd /tmp && pytest -q'

    def test_a_program_that_exists_is_not_second_guessed(self):
        assert agent_hooks.check_before('git stauts') is None

    def test_nothing_close_says_nothing(self):
        assert agent_hooks.check_before('zzzzqqqq now') is None

    def test_two_missing_programs_are_left_to_the_shell(self):
        assert agent_hooks.check_before('gti status && grpe x') is None

    @pytest.mark.parametrize('script', ['', '   ', None, 42])
    def test_not_a_command(self, script):
        assert agent_hooks.check_before(script) is None


GIT_SATUS = ("Exit code 1\ngit: 'satus' is not a git command. See 'git --help'."
             '\n\nThe most similar command is\n\tstatus\n')


class TestNoteAfter(object):
    def test_the_suggestion_and_its_confidence(self):
        note = agent_hooks.note_after(
            'git satus', agent_hooks._output_from_error(GIT_SATUS))
        assert note.startswith('The Bleep suggests: `git status` (95% confidence')

    def test_a_diagnosis_when_there_is_one(self):
        output = ('Error: listen EADDRINUSE: address already in use :::3000\n')
        note = agent_hooks.note_after('node server.js', output)
        assert 'Diagnosis:' in note
        assert 'next: `' in note

    def test_no_output_no_note(self):
        assert agent_hooks.note_after('git satus', None) is None

    def test_nothing_recognised_no_note(self):
        assert agent_hooks.note_after('true', 'some unrelated words') is None

    def test_the_note_is_bounded(self, mocker):
        mocker.patch.object(agent_hooks, 'MAX_NOTE', 40)
        note = agent_hooks.note_after(
            'git satus', agent_hooks._output_from_error(GIT_SATUS))
        assert len(note) == 40 and note.endswith(u'…')


class TestOutputFromError(object):
    def test_the_exit_code_line_is_dropped(self):
        assert agent_hooks._output_from_error('Exit code 2\nbad thing\nmore') \
            == 'bad thing\nmore'

    def test_a_shell_that_never_started_has_no_output(self):
        assert agent_hooks._output_from_error('spawn /bin/bash ENOENT') is None
        assert agent_hooks._output_from_error('') is None
        assert agent_hooks._output_from_error(None) is None


class TestClaudeCode(object):
    def pre(self, command, tool='Bash'):
        return {'hook_event_name': 'PreToolUse', 'tool_name': tool,
                'tool_input': {'command': command, 'description': 'x'},
                'cwd': '/tmp', 'session_id': 'abc'}

    def test_a_misspelled_program_is_refused_with_the_fix(self):
        answer = agent_hooks.handle('claude-code', self.pre('gti status'))
        out = answer['hookSpecificOutput']
        assert out['hookEventName'] == 'PreToolUse'
        assert out['permissionDecision'] == 'deny'
        assert '`git status`' in out['permissionDecisionReason']
        assert 'updatedInput' not in out

    def test_ask_and_context_modes(self, os_environ):
        os_environ[agent_hooks.DECISION_ENV] = 'ask'
        out = agent_hooks.handle('claude-code', self.pre('gti status'))
        assert out['hookSpecificOutput']['permissionDecision'] == 'ask'
        os_environ[agent_hooks.DECISION_ENV] = 'context'
        out = agent_hooks.handle('claude-code', self.pre('gti status'))
        assert 'permissionDecision' not in out['hookSpecificOutput']
        assert '`git status`' in out['hookSpecificOutput']['additionalContext']

    def test_an_unknown_mode_is_the_default(self, os_environ):
        os_environ[agent_hooks.DECISION_ENV] = 'explode'
        out = agent_hooks.handle('claude-code', self.pre('gti status'))
        assert out['hookSpecificOutput']['permissionDecision'] == 'deny'

    def test_a_good_command_gets_no_opinion(self):
        assert agent_hooks.handle('claude-code', self.pre('git status')) is None

    def test_other_tools_are_none_of_its_business(self):
        assert agent_hooks.handle('claude-code', self.pre('gti', 'Edit')) is None

    def test_a_failure_gets_a_note(self):
        payload = {'hook_event_name': 'PostToolUseFailure', 'tool_name': 'Bash',
                   'tool_input': {'command': 'git satus'},
                   'error': GIT_SATUS, 'is_interrupt': False}
        out = agent_hooks.handle('claude-code', payload)['hookSpecificOutput']
        assert out['hookEventName'] == 'PostToolUseFailure'
        assert out['additionalContext'].startswith(
            'The Bleep suggests: `git status`')

    def test_an_interrupted_command_is_not_a_failure_to_explain(self):
        payload = {'hook_event_name': 'PostToolUseFailure', 'tool_name': 'Bash',
                   'tool_input': {'command': 'git satus'},
                   'error': GIT_SATUS, 'is_interrupt': True}
        assert agent_hooks.handle('claude-code', payload) is None

    def test_a_success_event_is_ignored(self):
        payload = {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash',
                   'tool_input': {'command': 'git satus'},
                   'tool_response': {'stdout': ''}}
        assert agent_hooks.handle('claude-code', payload) is None


class TestCursor(object):
    def test_a_misspelled_program_is_refused(self):
        out = agent_hooks.handle('cursor', {
            'hook_event_name': 'beforeShellExecution',
            'command': 'gti status', 'cwd': '/tmp', 'sandbox': False})
        assert out['permission'] == 'deny'
        assert out['user_message'] == '`gti` looks like `git status`'
        assert '`git status`' in out['agent_message']

    def test_context_mode_allows(self, os_environ):
        os_environ[agent_hooks.DECISION_ENV] = 'context'
        out = agent_hooks.handle('cursor', {
            'hook_event_name': 'beforeShellExecution', 'command': 'gti status'})
        assert out['permission'] == 'allow'

    def test_other_events_are_ignored(self):
        assert agent_hooks.handle('cursor', {
            'hook_event_name': 'afterShellExecution',
            'command': 'gti status', 'output': 'x'}) is None


class TestRun(object):
    def test_reads_stdin_writes_one_json_line(self):
        stdin = io.StringIO(json.dumps({
            'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
            'tool_input': {'command': 'gti status'}}))
        stdout = io.StringIO()
        assert agent_hooks.run('claude-code', stdin, stdout) == 0
        answer = json.loads(stdout.getvalue())
        assert answer['hookSpecificOutput']['permissionDecision'] == 'deny'

    def test_nothing_to_say_writes_nothing(self):
        stdout = io.StringIO()
        assert agent_hooks.run('claude-code', io.StringIO(json.dumps({
            'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
            'tool_input': {'command': 'git status'}})), stdout) == 0
        assert stdout.getvalue() == ''

    @pytest.mark.parametrize('garbage', ['', 'not json', '[1, 2]', '{"a":'])
    def test_garbage_never_blocks_the_agent(self, garbage):
        """Exit 2 or a crash would block the agent's command; a corrector
        that cannot read its input says nothing and exits 0."""
        stdout = io.StringIO()
        assert agent_hooks.run('claude-code', io.StringIO(garbage), stdout) == 0
        assert stdout.getvalue() == ''

    def test_an_unknown_agent(self, capsys):
        assert agent_hooks.run('copilot', io.StringIO('{}'), io.StringIO()) == 2
        assert 'Unknown agent' in capsys.readouterr()[1]


class TestConfig(object):
    def test_claude_code_settings_shape(self, mocker):
        mocker.patch('thebleep.invocation.command', return_value='thebleep')
        text, where = agent_hooks.config('claude-code')
        settings = json.loads(text)
        for event in ('PreToolUse', 'PostToolUseFailure'):
            (group,) = settings['hooks'][event]
            assert group['matcher'] == 'Bash|PowerShell'
            (hook,) = group['hooks']
            assert hook == {'type': 'command', 'timeout': 10,
                            'command': 'thebleep --as-hook claude-code'}
        assert '~/.claude/settings.json' in where

    def test_cursor_hooks_file_shape(self, mocker):
        mocker.patch('thebleep.invocation.command', return_value='thebleep')
        text, where = agent_hooks.config('cursor')
        settings = json.loads(text)
        assert settings['version'] == 1
        (hook,) = settings['hooks']['beforeShellExecution']
        assert hook == {'command': 'thebleep --as-hook cursor', 'timeout': 10}
        assert '~/.cursor/hooks.json' in where

    def test_the_program_is_how_this_installation_is_run(self, mocker):
        mocker.patch('thebleep.invocation.command',
                     return_value='/opt/py/bin/python /src/thebleep/__main__.py')
        text, _ = agent_hooks.config('cursor')
        assert '/opt/py/bin/python /src/thebleep/__main__.py --as-hook cursor' \
            in text

    def test_print_config_goes_to_stdout_and_stderr(self, capsys, mocker):
        mocker.patch('thebleep.invocation.command', return_value='thebleep')
        assert agent_hooks.print_config('claude-code') == 0
        out, err = capsys.readouterr()
        assert json.loads(out)['hooks']
        assert 'Merge this into' in err
        assert agent_hooks.print_config('nope') == 2
