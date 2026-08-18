# -*- encoding: utf-8 -*-

"""Deciding whether the previous command may run a second time.

The invariant under test: nothing runs again unless running it cannot have an
effect, or the user said it could.

"""

import os
import sys
import pexpect
import pytest
import thebleep
from thebleep import replay


@pytest.fixture
def on_path(mocker):
    """A machine where these programs exist and nothing else does."""
    installed = {'ls', 'cat', 'grep', 'git', 'apt-get', 'reboot', 'deploy',
                 'sort', 'find', 'sed', 'awk', 'tree', 'docker', 'npm', 'env'}

    def which(name):
        return '/usr/bin/' + name if name.split('/')[-1] in installed else None

    return mocker.patch('thebleep.utils.which', side_effect=which)


@pytest.mark.usefixtures('on_path')
class TestIsInert(object):
    """`is_inert` is the only thing allowed to skip the question, so it has to
    be right in the direction of saying no."""

    @pytest.mark.parametrize('script', [
        # Nothing to run: the shell will fail to find it exactly as before.
        'gti status',
        'puthon script.py',
        'ehco test',
        'sl -l',
        # Reads whatever it is asked to do.
        'ls',
        'ls -lah /nowhere',
        'cat a b c',
        'grep -r pattern .',
        '/bin/ls -l',
        '/usr/bin/grep x f',
        # Variables set for a command that only reads.
        'LC_ALL=C ls -l',
        'GIT_TRACE=1 LANG=C grep x f',
        # Assignments and nothing else: a subshell throws them away.
        'FOO=bar',
    ])
    def test_inert(self, script):
        assert replay.is_inert(script)

    @pytest.mark.parametrize('script', [
        # Could do anything, and did once already.
        'reboot',
        'deploy production',
        'git push',
        'git branch -d topic',
        'apt-get install vim',
        'docker run -d nginx',
        'npm install',
        # On the list of things that read, but not with these arguments.
        'sort -o out in',
        'sed -i s/a/b/ f',
        'find . -delete',
        'tree -o out',
        'env FOO=bar deploy',
        # Redirection, chaining, substitution, backgrounding: the program name
        # no longer says what the script does.
        'ls > listing',
        'ls >> listing',
        'cat f > g',
        'grep x f | tee out',
        'ls && deploy',
        'ls; deploy',
        'ls || deploy',
        'ls `deploy`',
        'ls $(deploy)',
        'ls &',
        'ls\ndeploy',
        '(deploy)',
        # `sh` runs these without consulting PATH, so "not found" means
        # nothing about them.
        '. ./deploy.sh',
        'source ./deploy.sh',
        'eval deploy',
        'exec deploy',
        'command deploy',
        # A builtin in every shell, even where /usr/bin/kill is missing.
        'kill -9 1234',
        # Nothing to decide about.
        '',
        '   ',
    ])
    def test_not_inert(self, script):
        assert not replay.is_inert(script)

    @pytest.mark.parametrize('script', [
        # The program name comes out of an expansion, so it is not `ls`.
        '$X ls',
        '${X} ls',
        # Quoted, escaped or globbed: `sh` runs `deploy`, but looking the
        # literal text up on PATH finds nothing at all.
        '"deploy"',
        "'deploy'",
        '\\deploy',
        'depl*y',
        'depl?y',
        '~/bin/deploy',
    ])
    def test_a_program_name_that_is_not_literal_is_never_inert(self, script):
        assert not replay.is_inert(script)

    def test_an_argument_may_expand_freely(self):
        """After expansion `sh` does not go looking for operators again, so a
        variable in an argument cannot turn `ls` into something else."""
        assert replay.is_inert('ls $HOME')
        assert replay.is_inert('grep -r "$PATTERN" .')


@pytest.mark.usefixtures('on_path')
class TestIsAllowed(object):
    @pytest.fixture
    def ask(self, mocker):
        return mocker.patch('thebleep.replay._ask', return_value=False)

    @pytest.fixture
    def interactive(self, mocker):
        return mocker.patch('thebleep.ui.is_interactive', return_value=True)

    def test_an_inert_command_is_not_asked_about(self, ask, settings):
        settings.confirm_replay = True
        assert replay.is_allowed('ls -l', 'ls -l')
        assert not ask.called

    def test_anything_else_is_asked_about(self, ask, settings, interactive):
        settings.confirm_replay = True
        assert not replay.is_allowed('deploy', 'deploy')
        ask.assert_called_once_with('deploy')

    def test_saying_yes_allows_it(self, ask, settings, interactive):
        settings.confirm_replay = True
        ask.return_value = True
        assert replay.is_allowed('deploy', 'deploy')

    def test_with_no_terminal_it_is_refused(self, ask, settings, mocker):
        """There is nobody to ask, so the safe answer is the only answer."""
        mocker.patch('thebleep.ui.is_interactive', return_value=False)
        settings.confirm_replay = True
        assert not replay.is_allowed('deploy', 'deploy')
        assert not ask.called

    def test_turning_the_question_off_restores_the_old_behaviour(self, ask,
                                                                 settings):
        settings.confirm_replay = False
        assert replay.is_allowed('deploy', 'deploy')
        assert not ask.called

    def test_the_expanded_script_is_what_gets_judged(self, ask, settings,
                                                     interactive):
        """An alias hides what really runs, so the expansion is the subject."""
        settings.confirm_replay = True
        assert not replay.is_allowed('ll', 'deploy production')
        assert replay.is_allowed('ll', 'ls -lah')

    def test_the_question_names_what_would_run(self, ask, settings,
                                               interactive):
        """Asking about `ll` would not tell the user what they are agreeing
        to."""
        replay.is_allowed('ll', 'deploy production')
        ask.assert_called_once_with('deploy production')


class TestAsk(object):
    @pytest.fixture(autouse=True)
    def get_key(self, mocker):
        return mocker.patch('thebleep.system.get_key')

    @pytest.mark.parametrize('key, expected', [
        ('y', True),
        ('Y', True),
        ('n', False),
        ('N', False),
        # Anything that is not yes is no, including a stray key and ctrl+c.
        ('\n', False),
        ('\x03', False),
        ('q', False),
        ('', False),
    ])
    def test_only_yes_means_yes(self, get_key, key, expected):
        get_key.return_value = key
        assert replay._ask('deploy') is expected


class TestTheSideEffectItself(object):
    """The whole point, end to end: a command that leaves a mark behind must
    not leave a second one without being agreed to."""

    @pytest.fixture
    def side_effect(self, tmpdir, os_environ):
        """A command that records having run, then fails."""
        marks = tmpdir.join('marks')
        script = tmpdir.join('leaves-a-mark')
        script.write('#!/bin/sh\n'
                     'echo ran >> "{}"\n'
                     'echo "leaves-a-mark: it went wrong" >&2\n'
                     'exit 1\n'.format(marks))
        script.chmod(0o755)
        os_environ['PATH'] = str(tmpdir) + ':' + os_environ['PATH']
        return marks

    def _run_it_once(self, side_effect):
        import subprocess
        subprocess.call(['leaves-a-mark'], stderr=subprocess.DEVNULL)
        assert side_effect.read().count('ran') == 1

    def test_it_does_not_run_again_unasked(self, side_effect, settings,
                                           mocker):
        from thebleep.types import Command

        settings.confirm_replay = True
        # No terminal, so there is nobody to ask: it must not run.
        mocker.patch('thebleep.ui.is_interactive', return_value=False)

        self._run_it_once(side_effect)
        command = Command.from_raw_script(['leaves-a-mark'])

        assert side_effect.read().count('ran') == 1, \
            'the command ran a second time without being asked about'
        assert command.output is None

    def test_it_runs_again_once_agreed_to(self, side_effect, settings, mocker):
        from thebleep.types import Command

        settings.confirm_replay = True
        mocker.patch('thebleep.ui.is_interactive', return_value=True)
        mocker.patch('thebleep.replay._ask', return_value=True)

        self._run_it_once(side_effect)
        command = Command.from_raw_script(['leaves-a-mark'])

        assert side_effect.read().count('ran') == 2
        assert 'it went wrong' in command.output


@pytest.mark.skipif(sys.platform == 'win32',
                    reason='needs a pty to be asked anything')
class TestTheQuestionOnARealTerminal(object):
    """The question is written without a trailing newline and is followed by a
    blocking read, so only a real terminal shows whether it arrives at all: an
    unflushed prompt leaves the user staring at nothing while it waits."""

    @pytest.fixture
    def ask_about(self, tmpdir):
        marks = tmpdir.join('marks')
        script = tmpdir.join('leaves-a-mark')
        script.write('#!/bin/sh\n'
                     'echo ran >> "{}"\n'
                     'echo "leaves-a-mark: it went wrong" >&2\n'
                     'exit 1\n'.format(marks))
        script.chmod(0o755)

        def run(answer):
            marks.write('')
            environment = dict(os.environ,
                               PATH=str(tmpdir) + os.pathsep + os.environ['PATH'],
                               PYTHONPATH=os.path.dirname(os.path.dirname(
                                   os.path.abspath(thebleep.__file__))),
                               XDG_CONFIG_HOME=str(tmpdir.mkdir('config')),
                               XDG_CACHE_HOME=str(tmpdir.mkdir('cache')),
                               TB_SHELL='bash')
            child = pexpect.spawn(
                sys.executable,
                ['-c', 'import sys; sys.argv = ["thebleep", "leaves-a-mark"];'
                       'from thebleep.entrypoints.main import main; main()'],
                env=environment, encoding='utf-8', timeout=30)
            try:
                child.expect('Run it')
                child.send(answer)
                child.expect(pexpect.EOF)
            finally:
                child.close(force=True)
            return len(marks.read().split())

        return run

    def test_the_question_reaches_the_terminal_and_no_means_no(self,
                                                               ask_about):
        assert ask_about('n') == 0

    def test_yes_means_yes(self, ask_about):
        assert ask_about('y') == 1
