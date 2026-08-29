# -*- encoding: utf-8 -*-

import os
import pytest
import sys
from subprocess import TimeoutExpired
from tempfile import TemporaryFile
from unittest.mock import Mock, patch
from psutil import AccessDenied

from thebleep.output_readers import rerun


def _popen(output=b'', timeout=False):
    """A stand-in for a command that is running.

    Its stdout is something really readable rather than a mock, because that is
    what the reader thread reads: `_wait_output` drains it while the command
    runs and keeps only the tail, which is not something `communicate` can be
    asked for.

    A temporary file rather than a pipe, so that a test can hand over more than
    a pipe would hold -- writing 64KB into a pipe nobody is reading yet blocks
    the test itself.

    """
    stdout = TemporaryFile()
    stdout.write(output)
    stdout.seek(0)

    popen = Mock(pid=1234)
    popen.stdout = stdout
    popen.stdin = None
    if timeout:
        popen.wait.side_effect = [TimeoutExpired('cmd', 3), 0]
    else:
        popen.wait.return_value = 0
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

    @patch('thebleep.output_readers.rerun.Popen',
           side_effect=OSError('program disappeared'))
    def test_a_program_that_disappears_before_launch_is_not_a_traceback(
            self, popen_mock):
        assert rerun.get_output('ls', 'ls') is None

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
        assert popen.wait.call_args[1]['timeout'] \
            == settings.wait_slow_command

    def test_wait_output_is_not_slow(self, settings):
        popen = _popen(b'output')
        assert rerun._wait_output(popen, False) == b'output'
        assert popen.wait.call_args[1]['timeout'] == settings.wait_command

    def test_wait_output_reads_while_the_command_runs(self):
        """A command that fills the pipe buffer blocks until someone reads it,
        so waiting for it to exit before reading is a deadlock.

        Which is why the reading happens in a thread that starts before the
        wait, rather than after it.

        """
        popen = _popen(b'a lot of output' * 100000)
        assert rerun._wait_output(popen, False).endswith(b'output')

    def test_wait_output_keeps_the_end_of_a_huge_output(self):
        """The timeout bounds the *time* a command has to print, not the number
        of bytes -- a test suite in a loop can put hundreds of megabytes through
        the pipe in three seconds, and all of it used to be accumulated in
        memory and then decoded into a second copy of itself."""
        limit = 4096
        with patch.object(rerun, 'MAX_OUTPUT', limit):
            popen = _popen(b'x' * 100000 + b'the error is here')
            output = rerun._wait_output(popen, False)
        assert len(output) == limit
        assert output.endswith(b'the error is here')

    def test_wait_output_closes_stdin(self):
        """`communicate` used to do this. A command left waiting for input
        nobody is going to send waits for the whole timeout."""
        popen = _popen(b'output')
        popen.stdin = Mock()
        rerun._wait_output(popen, False)
        popen.stdin.close.assert_called_once_with()

    @patch('thebleep.output_readers.rerun._kill_process')
    def test_wait_output_timeout(self, kill_process_mock):
        assert rerun._wait_output(_popen(timeout=True), False) is None
        kill_process_mock.assert_called_once_with(self.proc_mock)

    @patch('thebleep.output_readers.rerun._kill_process')
    def test_wait_output_joins_the_reader_after_timeout(self,
                                                        kill_process_mock,
                                                        mocker):
        reader = mocker.patch('threading.Thread').return_value
        assert rerun._wait_output(_popen(timeout=True), False) is None
        reader.join.assert_called_once_with(1)

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
    def test_kill_process_that_has_already_gone(self, logs_mock):
        """The ordinary way a process tree comes apart under a timeout: a child
        exits between being listed and being killed. Only `AccessDenied` was
        caught, so that race came out of a timeout as a traceback."""
        from psutil import NoSuchProcess

        proc = Mock(pid=123)
        proc.kill.side_effect = NoSuchProcess(123)
        rerun._kill_process(proc)
        assert not logs_mock.debug.called

    def test_kill_tree_when_the_tree_has_already_gone(self):
        """`children()` walks a tree that is moving, and can raise too."""
        from psutil import NoSuchProcess

        self.proc_mock.children.side_effect = NoSuchProcess(1234)
        popen = _popen()
        rerun._kill_tree(popen)
        popen.kill.assert_called_once_with()

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

    def test_somebody_elses_tb_variable_survives(self, os_environ):
        """This was scrubbed by `TB_` prefix, and `TB_` is short enough to
        belong to somebody else -- a build system, an in-house tool. Deleting a
        stranger's variable makes the command behave differently the second time
        for a reason nobody could find, so the transport is scrubbed by name."""
        child = self._child_env(TB_APP_ENDPOINT='prod')
        assert child['TB_APP_ENDPOINT'] == 'prod'
        assert 'TB_HISTORY' not in child

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


@pytest.mark.skipif(sys.platform == 'win32',
                    reason='needs a POSIX shell that is not /bin/sh')
class TestWhichShellTheReplayRunsIn(object):
    """`Popen(shell=True)` is the *platform's* shell, not the user's.

    On POSIX that is `/bin/sh` -- dash on Debian and Ubuntu -- whatever shell
    the command actually failed in. So a bash-ism came back as an `sh` error and
    The Bleep corrected a problem the user never had:

        $ [[ -f /nope ]]                # bash: exits 1, prints nothing
        $ bleep
        /bin/sh: 1: [[: not found       # a different error entirely

    """

    BASHISM = '[[ -f /definitely/not/here ]]'

    def test_the_old_way_gets_somebody_elses_error(self):
        """Guards the guard: without this, the test below proves nothing."""
        import subprocess

        done = subprocess.run(self.BASHISM, shell=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=10)
        if b'[[' not in done.stdout:
            pytest.skip('/bin/sh on this machine understands `[[`')

    def test_bash_gets_bash(self, os_environ, settings):
        os_environ['TB_SHELL'] = 'bash'
        settings.env = {}
        from thebleep.shells import shell

        if shell.friendly_name != 'Bash':
            pytest.skip('the shell could not be forced to bash')

        assert rerun._call(self.BASHISM) == (
            ['bash', '-c', self.BASHISM], False)
        assert rerun.get_output(self.BASHISM, self.BASHISM) == ''

    def test_a_shell_that_will_not_say_falls_back(self, mocker, settings):
        """Which is what this always did, so nothing is lost by not knowing."""
        from thebleep.shells import shell

        mocker.patch.object(type(shell), 'replay_argv', return_value=None)
        assert rerun._call('echo hi') == ('echo hi', True)

    def test_and_a_shell_that_raises_does_too(self, mocker):
        from thebleep.shells import shell

        mocker.patch.object(type(shell), 'replay_argv',
                            side_effect=RuntimeError)
        assert rerun._call('echo hi') == ('echo hi', True)


def test_a_shell_that_is_not_installed_falls_back(mocker, settings):
    """`TB_SHELL` says which shell the command was typed in, not that this
    machine can start another one of it.

    A Windows runner with `TB_SHELL=bash` and no bash on `PATH` got a `Popen`
    that raised, so the correction had no output at all and answered
    `No bleeps given` -- which is worse than the wrong shell, because the wrong
    shell at least printed something a rule could read.

    """
    from thebleep.shells import shell

    mocker.patch.object(type(shell), 'replay_argv',
                        return_value=['no-such-shell', '-c', 'echo hi'])
    assert rerun._call('echo hi') == ('echo hi', True)
