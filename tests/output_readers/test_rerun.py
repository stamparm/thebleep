# -*- encoding: utf-8 -*-

import os
import pytest
import sys
from subprocess import TimeoutExpired
from unittest.mock import Mock, patch
from psutil import AccessDenied

from thebleep.output_readers import rerun


def _popen(output=b'', timeout=False):
    """A stand-in for a command that is running."""
    popen = Mock(pid=1234)
    if timeout:
        popen.communicate.side_effect = [TimeoutExpired('cmd', 3), (b'', None)]
    else:
        popen.communicate.return_value = (output, None)
    return popen


class TestRerun(object):
    def setup_method(self, test_method):
        # `rerun` imports psutil when it needs it, so the patch goes there.
        self.patcher = patch('psutil.Process')
        process_mock = self.patcher.start()
        self.proc_mock = process_mock.return_value = Mock()
        self.proc_mock.children.return_value = []

    def teardown_method(self, test_method):
        self.patcher.stop()

    @patch('thebleep.output_readers.rerun._wait_output', return_value=None)
    @patch('thebleep.output_readers.rerun.Popen')
    def test_get_output(self, popen_mock, wait_output_mock):
        assert rerun.get_output('', '') is None
        wait_output_mock.assert_called_once()

    @patch('thebleep.output_readers.rerun.Popen')
    def test_get_output_invalid_continuation_byte(self, popen_mock):
        output = b'ls: illegal option -- \xc3\nusage: ls [-@ABC...] [file ...]\n'
        expected = u'ls: illegal option -- �\nusage: ls [-@ABC...] [file ...]\n'
        popen_mock.return_value = _popen(output)
        assert rerun.get_output('', '') == expected

    @patch('thebleep.output_readers.rerun._wait_output', return_value=None)
    @patch('thebleep.output_readers.rerun.Popen')
    def test_get_output_doesnt_log_whole_env(self, popen_mock,
                                             wait_output_mock, settings,
                                             os_environ, capsys):
        settings.debug = True
        os_environ['SECRET_TOKEN'] = 'secret-value'
        rerun.get_output('ls', 'ls')
        assert 'secret-value' not in capsys.readouterr()[1]

    @pytest.mark.skipif(sys.platform == 'win32', reason="skip when running on Windows")
    @patch('thebleep.output_readers.rerun._wait_output', return_value=b'')
    def test_get_output_unicode_misspell(self, wait_output_mock):
        rerun.get_output(u'pácman', u'pácman')
        wait_output_mock.assert_called_once()

    @patch('thebleep.output_readers.rerun.Popen')
    def test_get_output_with_an_unbalanced_quote(self, popen_mock):
        """A command with a quote left open is a thing people mistype."""
        popen_mock.return_value = _popen(b'sh: unexpected EOF')
        assert rerun.get_output('echo "oops', 'echo "oops') \
            == 'sh: unexpected EOF'

    def test_wait_output_is_slow(self, settings):
        popen = _popen(b'output')
        assert rerun._wait_output(popen, True) == b'output'
        assert popen.communicate.call_args[1]['timeout'] \
            == settings.wait_slow_command

    def test_wait_output_is_not_slow(self, settings):
        popen = _popen(b'output')
        assert rerun._wait_output(popen, False) == b'output'
        assert popen.communicate.call_args[1]['timeout'] \
            == settings.wait_command

    def test_wait_output_reads_while_the_command_runs(self):
        """A command that fills the pipe buffer blocks until someone reads it,
        so waiting for it to exit before reading is a deadlock."""
        popen = _popen(b'a lot of output')
        rerun._wait_output(popen, False)
        assert popen.communicate.called
        assert not popen.stdout.read.called

    @patch('thebleep.output_readers.rerun._kill_process')
    def test_wait_output_timeout(self, kill_process_mock):
        assert rerun._wait_output(_popen(timeout=True), False) is None
        kill_process_mock.assert_called_once_with(self.proc_mock)

    @patch('thebleep.output_readers.rerun._kill_process')
    def test_wait_output_timeout_children(self, kill_process_mock):
        self.proc_mock.children.return_value = [Mock()] * 2
        assert rerun._wait_output(_popen(timeout=True), False) is None
        assert kill_process_mock.call_count == 3

    def test_kill_process(self):
        proc = Mock()
        rerun._kill_process(proc)
        proc.kill.assert_called_once_with()

    @patch('thebleep.output_readers.rerun.logs')
    def test_kill_process_access_denied(self, logs_mock):
        proc = Mock()
        proc.kill.side_effect = AccessDenied()
        rerun._kill_process(proc)
        proc.kill.assert_called_once_with()
        logs_mock.debug.assert_called_once()

    @patch('thebleep.output_readers.rerun.logs')
    def test_kill_process_access_denied_when_exe_is_denied(self, logs_mock):
        proc = Mock(pid=123)
        proc.kill.side_effect = AccessDenied()
        proc.exe.side_effect = AccessDenied()
        rerun._kill_process(proc)
        proc.kill.assert_called_once_with()
        logs_mock.debug.assert_called_once()


# What the shell alias puts in the environment on its way in. `TB_HISTORY` and
# `TB_SHELL_ALIASES` are the interesting ones: they are the user's last ten
# commands and their alias list, and nothing outside The Bleep should see them.
TRANSPORT = {
    'TB_SHELL': 'bash',
    'TB_ALIAS': 'bleep',
    'TB_HISTORY': 'ssh prod.internal\ngit commit -m wip\nAWS_KEY=AKIAsecret x',
    'TB_SHELL_ALIASES': "alias deploy='ssh prod && ./deploy.sh'",
    'TB_CMD': 'bleep',
}


@pytest.mark.skipif(sys.platform == 'win32',
                    reason='needs a POSIX shell to read the environment back')
class TestReplayedEnvironment(object):
    """What a command being run a second time is allowed to see.

    These run a real shell rather than inspecting the environment we would have
    passed it: the point is what the child process ends up with.

    """

    def _child_env(self, script='env', **environ):
        os.environ.update(TRANSPORT)
        os.environ.update(environ)
        output = rerun.get_output(script, script)
        return dict(line.split('=', 1)
                    for line in output.split('\n') if '=' in line)

    def test_transport_is_not_inherited(self, os_environ):
        """The user's history and aliases are not the child's business."""
        child = self._child_env()
        leaked = [name for name in child if name.startswith('TB_')]
        assert leaked == []
        assert 'AKIAsecret' not in '\n'.join(child.values())
        assert './deploy.sh' not in '\n'.join(child.values())

    def test_the_rest_of_the_environment_survives(self, os_environ):
        """Only the transport goes; what the command originally had stays."""
        child = self._child_env(MY_TOKEN='keep-me')
        assert child['MY_TOKEN'] == 'keep-me'

    def test_git_tracing_reaches_git(self, os_environ, tmpdir):
        """Through a `git` on PATH that reports what it was given."""
        shim = tmpdir.join('git')
        shim.write('#!/bin/sh\nenv\n')
        os.chmod(str(shim), 0o755)
        os.environ['PATH'] = '{}{}{}'.format(
            str(tmpdir), os.pathsep, os.environ['PATH'])
        assert self._child_env('git status')['GIT_TRACE'] == '1'

    def test_git_tracing_does_not_go_to_anything_else(self, os_environ):
        """`GIT_TRACE` is a debugging switch, and git is not the only reader."""
        assert 'GIT_TRACE' not in self._child_env('env')
        assert 'GIT_TRACE' not in self._child_env('LC_ALL=C env')

    def test_git_tracing_survives_an_unparseable_script(self, os_environ):
        assert 'GIT_TRACE' not in self._child_env('env "')


@pytest.mark.parametrize('program, traced', [
    ('git', True),
    ('/usr/bin/git', True),
    ('hub', True),
    ('env', False),
    ('gitk', False),
    ('legit', False),
    (None, False),
])
def test_child_environment_traces_git_only(os_environ, program, traced):
    assert ('GIT_TRACE' in rerun._child_environment(program)) is traced
