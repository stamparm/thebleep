# -*- encoding: utf-8 -*-

"""`why_command`: a program of the user's choosing, asked once, when `--why`
had nothing deterministic to say."""

import sys

import pytest

from thebleep import explainer

# A program that answers with what it was given, so the contract -- command in
# the environment, output on stdin -- is what is tested.
ECHO = (sys.executable + ' -c "import os, sys; print(\'cmd=\' + '
        'os.environ[\'THEBLEEP_FAILED_COMMAND\']); print(\'exit=\' + '
        'os.environ[\'THEBLEEP_FAILED_EXIT\']); '
        'print(\'saw=\' + sys.stdin.read().strip())"')


@pytest.fixture(autouse=True)
def a_posix_shell(mocker):
    mocker.patch('thebleep.shells.shell.replay_argv',
                 side_effect=lambda command: ['/bin/sh', '-c', command])


class TestConfigured(object):
    def test_off_by_default(self, settings):
        assert explainer.configured() is None

    @pytest.mark.parametrize('value', ['', '   ', None, 42, True])
    def test_only_a_command_counts(self, settings, value):
        settings.why_command = value
        assert explainer.configured() is None

    def test_a_command(self, settings):
        settings.why_command = '  ollama run llama3 '
        assert explainer.configured() == 'ollama run llama3'


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
class TestAsk(object):
    def test_the_contract(self, settings):
        settings.why_command = ECHO
        answer = explainer.ask('git satus', 'git: satus is not a git command',
                               exit_status='1')
        assert answer == ('cmd=git satus\nexit=1\n'
                          'saw=git: satus is not a git command')

    def test_without_output_or_exit(self, settings):
        settings.why_command = ECHO
        assert explainer.ask('git satus', None) == 'cmd=git satus\nexit=\nsaw='

    def test_nothing_configured_asks_nothing(self, settings, mocker):
        run = mocker.patch('subprocess.run')
        assert explainer.ask('git satus', 'x') is None
        assert not run.called

    def test_a_silent_program_is_no_answer(self, settings):
        settings.why_command = 'true'
        assert explainer.ask('git satus', 'x') is None

    def test_a_program_that_is_not_there(self, settings):
        settings.why_command = '/nonexistent/explainer'
        assert explainer.ask('git satus', 'x') is None

    def test_a_program_that_failed_has_not_explained(self, settings):
        settings.why_command = 'echo partial; echo oops >&2; exit 3'
        assert explainer.ask('git satus', 'x') is None

    def test_a_slow_program_is_cut_off(self, settings):
        settings.why_command = 'sleep 5'
        assert explainer.ask('git satus', 'x', timeout=0.2) is None

    def test_the_answer_is_bounded(self, settings, mocker):
        mocker.patch.object(explainer, 'MAX_ANSWER', 10)
        settings.why_command = 'echo 0123456789abcdef'
        assert explainer.ask('git satus', 'x') == '0123456789'

    def test_the_output_fed_is_bounded(self, settings, mocker):
        mocker.patch.object(explainer, 'MAX_INPUT', 4)
        settings.why_command = 'cat'
        assert explainer.ask('git satus', 'abcdefgh') == 'abcd'

    def test_the_timeout_setting(self, settings, mocker):
        settings.why_command = 'true'
        settings.why_timeout = 7
        run = mocker.patch('subprocess.run', side_effect=OSError)
        explainer.ask('git satus', 'x')
        assert run.call_args[1]['timeout'] == 7


def test_the_heading_names_the_source(settings):
    settings.why_command = 'ollama run llama3'
    assert explainer.heading() == (
        'from ollama run llama3, which is not a deterministic source:')
