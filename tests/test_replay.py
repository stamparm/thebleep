# -*- encoding: utf-8 -*-

"""Deciding whether the previous command may run a second time.

The invariant under test: nothing runs again unless running it cannot have an
effect, or the user said it could.

"""

import os
import shutil
import subprocess
import sys
import pexpect
import pytest
import thebleep
from thebleep import const, replay


@pytest.fixture
def on_path(mocker):
    """A machine where these programs exist and nothing else does."""
    installed = {'ls', 'cat', 'grep', 'git', 'apt-get', 'reboot', 'deploy',
                 'sort', 'find', 'sed', 'awk', 'tree', 'docker', 'npm', 'env',
                 'cargo', 'kubectl', 'uv', 'xxd'}

    def which(name):
        return '/usr/bin/' + name if name.split('/')[-1] in installed else None

    return mocker.patch('thebleep.utils.which', side_effect=which)


@pytest.fixture
def subcommands(mocker):
    """What the dispatchers on this machine would say they can do.

    Stood in for wherever `is_inert` is the subject, so that no test depends on
    the git that happens to be installed or on the aliases in whatever
    repository it runs from. `TestAskingTheProgramItself` uses the real one.

    """
    known = {
        'git': frozenset(['status', 'push', 'branch', 'checkout', 'log',
                          'stash', 'st', 'tag', 'commit']),
        # As `cargo --list` answers: the names, their aliases, and the words of
        # the descriptions printed beside them.
        'cargo': frozenset(['build', 'test', 'publish', 'b', 'zoom',
                            'Compile', 'a', 'local', 'package']),
    }

    def answer(program, question):
        return known.get(os.path.basename(program))

    return mocker.patch('thebleep.replay._subcommands', side_effect=answer)


@pytest.mark.usefixtures('on_path', 'subcommands')
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
        # A subcommand git does not have, so it fails at dispatch again and
        # does nothing on the way -- which is the whole of the typo case.
        'git satus',
        'git stauts',
        'git chekout featuer',
        'git puhs origin main',
        'cargo buld --release',
        'cargo tset',
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
        # A subcommand git does have. Whether it writes depends on the flags,
        # which is why the subcommand existing is as far as this goes.
        'git status',
        'git stash',
        # An alias is a subcommand git has, and it can stand for anything at
        # all, including `!deploy.sh`.
        'git st',
        # Nothing dispatched yet, so nothing is known about what would run.
        'git',
        # git's own options come before the subcommand, and which of them take
        # a value is not something this tries to work out: read wrong, `/tmp`
        # is the subcommand and `git -C /tmp push` runs again unasked.
        'git -C /tmp satus',
        'git --git-dir /elsewhere/.git satus',
        'cargo build --release',
        'cargo publish',
        # An alias `cargo --list` named, which can be `!anything`.
        'cargo b',
        'cargo zoom',
        # A word out of a description rather than a name. Being over-inclusive
        # only costs a question, which is the direction to be wrong in.
        'cargo Compile',
        # Not a dispatcher this knows how to ask, so it is asked about.
        'npm instal',
        'docker pss',
        'kubectl gat pods',
        'uv piip install requests',
        'apt-get install vim',
        'docker run -d nginx',
        'npm install',
        # On the list of things that read, but not with these arguments.
        'sort -o out in',
        'sed -i s/a/b/ f',
        'find . -delete',
        'tree -o out',
        'env FOO=bar deploy',
        # An assignment in front of a command, even one that looks harmless.
        # `FOO=bar cmd` is one command with an environment of its own, and
        # every question this module asks about `cmd` is one whose answer that
        # environment can change -- `PATH=/tmp/mine git satus` had the
        # dispatcher probe asking a different git than the one that ran. See
        # `replay._assignments_change_everything`.
        'LC_ALL=C ls -l',
        'GIT_TRACE=1 LANG=C grep x f',
        'GIT_TRACE=1 git satus',
        # A path, even to the real one. `READ_ONLY` is a judgement about the
        # program conventionally called `ls`, and a path is the user naming a
        # *file* -- whose name says nothing about what it does. `./ls` written
        # for the occasion re-ran itself and doubled its side effect, and there
        # is no test that tells `/bin/ls` from `./ls` without trusting the very
        # thing in question. So a path costs a question.
        '/bin/ls -l',
        '/usr/bin/grep x f',
        './ls',
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


@pytest.mark.usefixtures('on_path', 'subcommands')
class TestASubcommandTheProgramDoesNotHave(object):
    """The one thing that may not go wrong here is claiming a command is inert
    when it is not, so every unclear answer has to come back as "ask"."""

    @pytest.mark.parametrize('answer, why', [
        (None, 'the program would not say, so nothing is known'),
        (frozenset(), 'an empty list is not an answer either'),
    ])
    def test_no_answer_asks(self, mocker, answer, why):
        mocker.patch('thebleep.replay._subcommands', return_value=answer)
        assert not replay.is_inert('git satus'), why

    def test_the_program_is_asked_once_and_only_when_it_is_needed(
            self, subcommands):
        """A program that only reads is decided without running anything."""
        replay.is_inert('ls -l')
        replay.is_inert('deploy production')
        assert not subcommands.called

        replay.is_inert('git satus')
        assert subcommands.call_count == 1

    def test_it_is_asked_the_question_the_list_names(self, subcommands):
        replay.is_inert('git satus')
        subcommands.assert_called_once_with('git', replay.DISPATCHERS['git'])

    def test_a_path_to_the_program_is_still_the_program(self, subcommands):
        """A path may name any executable, even when its basename is git."""
        assert not replay.is_inert('/usr/bin/git satus')
        assert not replay.is_inert('/usr/bin/git push')
        assert not subcommands.called

    def test_the_git_list_is_not_filtered(self):
        """`nohelpers` looks tidier and is an under-inclusion.

        It subtracts the eight `--`-suffixed commands, all of which dispatch, so
        `git web--browse http://x` looked like a typo and relaunched a browser
        without asking. A word missing from the list is the one direction this
        module may not be wrong in.

        """
        assert 'nohelpers' not in ' '.join(replay.DISPATCHERS['git'])

    def test_nothing_on_the_read_only_list_is_a_dispatcher(self):
        """A program on both lists would be decided by the wrong one, and the
        answer for a dispatcher is the narrower of the two."""
        assert not (replay.READ_ONLY & set(replay.DISPATCHERS))


@pytest.mark.parametrize('program, why', [
    ('npm', 'neither `npm help` nor `npm -l` lists the aliases, so `i` is '
            'missing from the list -- and `npm i` installs'),
    ('uv', '`uv --help` leaves its hidden subcommands out; '
           '`generate-shell-completion` is absent and dispatches anyway'),
    ('docker', 'a --help screen is a document for a person, not a promise '
               'about what the program accepts'),
    ('kubectl', 'the same, and neither has a listing that can be shown to be '
                'complete'),
])
def test_dispatchers_without_a_complete_listing(program, why):
    """These would be worth having and are not, for one reason.

    The list a program gives has to contain every word it will dispatch on. One
    that is missing looks like a typo, and its command then runs a second time
    unasked -- which is the one thing this module may not do. Over-inclusion is
    free; under-inclusion is the whole risk.

    """
    assert program not in replay.DISPATCHERS, why


class TestAskingTheProgramItself(object):
    """`_subcommands` runs a real program, so these do too."""

    def test_git_lists_its_own_subcommands(self):
        if not shutil.which('git'):
            pytest.skip('git is not installed')

        answer = replay._subcommands('git', replay.DISPATCHERS['git'])
        if answer is None:
            pytest.skip('git is older than 2.18, which has no --list-cmds')

        assert 'status' in answer
        assert 'push' in answer
        assert 'satus' not in answer
        # The `--`-suffixed helpers dispatch, so they have to be in the list.
        # `--list-cmds=...,nohelpers` drops them, which is why it is not asked
        # for; this is the assertion that would have caught that.
        assert any('--' in name for name in answer), \
            'the -- helpers are missing, so one of them would look like a typo'

    def test_a_git_alias_is_one_of_them(self, tmpdir, monkeypatch):
        """Which is why `git st` is asked about: an alias can stand for
        anything, `!deploy.sh` included."""
        if not shutil.which('git'):
            pytest.skip('git is not installed')

        repo = tmpdir.mkdir('repo')
        monkeypatch.chdir(repo)
        subprocess.call(['git', 'init', '-q', '.'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.call(['git', 'config', 'alias.deploy', '!echo would-run'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        answer = replay._subcommands('git', replay.DISPATCHERS['git'])
        if answer is None:
            pytest.skip('git is older than 2.18, which has no --list-cmds')

        assert 'deploy' in answer, 'an alias would be taken for a typo'

    def test_cargo_lists_its_own_subcommands(self):
        if not shutil.which('cargo'):
            pytest.skip('cargo is not installed')

        answer = replay._subcommands('cargo', replay.DISPATCHERS['cargo'])
        if answer is None:
            pytest.skip('this cargo would not answer --list')

        assert 'build' in answer
        assert 'b' in answer, 'an alias would be taken for a typo'
        assert 'buld' not in answer

    def test_a_program_that_is_not_there_says_nothing(self):
        assert replay._subcommands('nosuchprogram-9c4f', ('--list',)) is None

    @pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
    def test_a_program_that_fails_says_nothing(self):
        assert replay._subcommands('false', ('--list',)) is None

    @pytest.mark.skipif(sys.platform == 'win32', reason='needs sleep')
    def test_a_program_that_hangs_is_not_waited_for(self, monkeypatch):
        monkeypatch.setattr(replay, 'PROBE_TIMEOUT', 1)
        assert replay._subcommands('sleep', ('30',)) is None

    @pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX script')
    def test_a_truncated_listing_is_not_trusted(self, tmpdir, monkeypatch):
        """An incomplete listing could hide a real, effectful subcommand."""
        program = tmpdir.join('dispatcher')
        program.write('#!/bin/sh\nprintf "status-123456789\\n"\n')
        program.chmod(0o755)
        monkeypatch.setattr('thebleep.utils.TOOL_OUTPUT', 8)

        assert replay._subcommands(str(program), ('--list',)) is None


@pytest.mark.skipif(sys.platform == 'win32',
                    reason='needs a POSIX executable script')
def test_an_explicit_dispatcher_path_is_not_executed(tmpdir, monkeypatch):
    """A local `git`-named executable must not be probed for free."""
    marker = tmpdir.join('probed')
    program = tmpdir.join('git')
    program.write('#!/bin/sh\n'
                  'printf ran > "{}"\n'
                  'printf status\n'.format(marker))
    program.chmod(0o755)
    monkeypatch.chdir(tmpdir)

    assert not replay.is_inert('./git satus')
    assert not marker.check()


@pytest.mark.parametrize('program, effect', [
    ('uniq', 'takes an output file as its second operand'),
    ('file', '-C writes a compiled magic file'),
    ('info', '--output writes the page to a file'),
    ('less', 'runs whatever LESSOPEN names'),
    ('man', 'writes into the cat page cache'),
    ('more', 'a pager, like less'),
    ('bat', 'a pager, like less'),
    ('tldr', 'downloads pages and caches them'),
    ('ldd', 'its own manual page says not to, on an untrusted executable'),
])
def test_programs_that_only_look_like_they_read(program, effect):
    """These were on the list and do not meet its own bar.

    The bar is that no combination of flags makes the command change anything,
    which is a strong claim; a program that can be talked into writing a file or
    running another program is not on the list however usual its usual form is.

    """
    assert program not in replay.READ_ONLY, effect


@pytest.mark.skipif(sys.platform == 'win32', reason='needs LESSOPEN')
def test_less_really_does_run_a_program(tmpdir, os_environ):
    """Why `less` came off the list, demonstrated rather than asserted."""
    if not shutil.which('less'):
        pytest.skip('less is not installed')

    mark = tmpdir.join('lessopen-ran')
    preprocessor = tmpdir.join('preprocess')
    preprocessor.write('#!/bin/sh\necho ran >> "{}"\ncat "$1"\n'.format(mark))
    preprocessor.chmod(0o755)
    subject = tmpdir.join('subject')
    subject.write('hello\n')

    subprocess.call(['less', str(subject)],
                    env=dict(os.environ,
                             LESSOPEN='|{} %s'.format(str(preprocessor))),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL)

    assert mark.check(), 'LESSOPEN did not run, so this is no longer the reason'
    assert not replay.is_inert('less {}'.format(subject))


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
        # Anything that is not yes is no, including a stray key.
        ('\n', False),
        ('q', False),
        ('', False),
    ])
    def test_only_yes_means_yes(self, get_key, key, expected):
        get_key.return_value = key
        assert replay._ask('deploy') is expected

    @pytest.mark.parametrize('key', [
        const.KEY_CTRL_C, const.KEY_ESCAPE, const.KEY_UP, const.KEY_DOWN,
        const.KEY_CTRL_N, const.KEY_CTRL_P,
    ])
    def test_a_key_that_is_not_a_letter(self, get_key, key):
        """`get_key` does not always return a string.

        Ctrl+C, Escape and the arrows come back as the sentinel objects in
        `const.KEY_MAPPING`, and `.lower()` on one of those raised
        `AttributeError` -- so pressing Ctrl+C at this prompt, the obvious way
        to say "no, leave it alone", answered with a traceback.

        This test used to pass the *string* `\'\\x03\'` and so agreed with a
        contract the real function does not have. These are the real values.

        """
        get_key.return_value = key
        assert replay._ask('deploy') is False


class TestTheChokePoint(object):
    """The gate has to be the only way to the rerun, on every platform."""

    @pytest.fixture(autouse=True)
    def readers(self, mocker):
        mocker.patch('thebleep.output_readers.shell_logger.is_available',
                     return_value=False)
        return mocker.patch('thebleep.output_readers.rerun.get_output',
                            return_value='output')

    def test_a_refusal_stops_the_rerun(self, readers, mocker, settings):
        from thebleep import output_readers

        settings.instant_mode = False
        mocker.patch('thebleep.replay.is_allowed', return_value=False)
        assert output_readers.get_output('deploy', 'deploy') is None
        assert not readers.called, 'the rerun was reached anyway'

    def test_permission_lets_it_through(self, readers, mocker, settings):
        from thebleep import output_readers

        settings.instant_mode = False
        mocker.patch('thebleep.replay.is_allowed', return_value=True)
        assert output_readers.get_output('deploy', 'deploy') == 'output'
        readers.assert_called_once_with('deploy', 'deploy')

    def test_the_gate_is_asked_about_both_forms(self, readers, mocker,
                                                settings):
        """It judges the expansion and names it, so it needs both."""
        from thebleep import output_readers

        settings.instant_mode = False
        allowed = mocker.patch('thebleep.replay.is_allowed', return_value=True)
        output_readers.get_output('ll', 'ls -lah')
        allowed.assert_called_once_with('ll', 'ls -lah')

    def test_a_recorded_output_never_reaches_the_gate(self, readers, mocker,
                                                      settings):
        """Instant mode has the output already, so there is nothing to ask."""
        from thebleep import output_readers

        settings.instant_mode = True
        allowed = mocker.patch('thebleep.replay.is_allowed')
        mocker.patch('thebleep.output_readers.read_log.get_output',
                     return_value='recorded')
        assert output_readers.get_output('deploy', 'deploy') == 'recorded'
        assert not allowed.called
        assert not readers.called


@pytest.mark.skipif(sys.platform == 'win32',
                    reason='needs a shebang script to be the thing replayed')
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


@pytest.mark.usefixtures('on_path', 'subcommands')
class TestWhatTheShellSaidAboutIt(object):
    """The exit status of the command being corrected, which the alias hands
    over before anything else can clobber `$?`."""

    @pytest.fixture
    def exited(self, os_environ):
        def _with(status):
            if status is None:
                os_environ.pop(replay.EXIT_ENV, None)
            else:
                os_environ[replay.EXIT_ENV] = str(status)

        return _with

    @pytest.mark.parametrize('status', [127, 126])
    def test_the_shells_own_statuses_prove_nothing(self, exited, on_path,
                                                   status):
        """This used to be the other way round, and it was a real hole.

        127 is `command not found` and 126 is `cannot execute` *by convention*,
        when the shell is the one reporting them. Nothing stops a program from
        exiting with either, and the ones that do are exactly the ones that had
        already done something first:

            $ make install            # a recipe's command was missing, four
            make: cc: not found       # recipes having already run
            make: *** [install] Error 127
            $ bleep
            make install              # run again, unasked

        `npm run`, `sh -c`, and anything else that reports its child's status do
        the same. So the status is no longer consulted here at all -- the `PATH`
        lookup is the sound version of the same idea.

        """
        exited(status)
        assert not replay.is_inert('deploy production')
        assert not replay.is_inert('docker compose up')

    @pytest.mark.parametrize('status', [126, 127])
    def test_and_a_command_that_is_not_there_is_still_inert(self, exited,
                                                            on_path, status):
        """Which is the case the shortcut was there for, reached soundly."""
        exited(status)
        assert replay.is_inert('no-such-program-anywhere --with args')

    def test_a_command_that_worked_is_not_run_again(self, exited, settings):
        """`git tag v9` succeeds silently. Run it again and it says `already
        exists`, and the suggestion was `git tag --force v9` -- a correction to
        a problem the second run had just caused, from output the user never
        saw."""
        exited(0)
        settings.confirm_replay = True
        assert not replay.is_allowed('git tag v9', 'git tag v9')
        assert not replay.is_allowed('echo hi >> log', 'echo hi >> log')

    def test_and_is_not_even_asked_about(self, exited, settings, mocker):
        """There is nothing to gain by asking, so the question goes too."""
        exited(0)
        settings.confirm_replay = True
        ask = mocker.patch.object(replay, '_ask', return_value=True)
        mocker.patch('thebleep.ui.is_interactive', return_value=True)
        assert not replay.is_allowed('deploy production', 'deploy production')
        assert not ask.called

    def test_something_that_reads_is_still_read(self, exited, settings):
        """Asked after `is_inert`, on purpose: `ls` that printed nothing exited
        0 and is still worth re-reading, which is what keeps `ls -A` working."""
        exited(0)
        settings.confirm_replay = True
        assert replay.is_allowed('ls', 'ls')
        assert replay.is_allowed('cat f', 'cat f')

    @pytest.mark.parametrize('status', [1, 2, 128, 130])
    def test_a_failure_changes_nothing(self, exited, status):
        exited(status)
        assert replay.is_inert('git satus')
        assert not replay.is_inert('git push')

    def test_an_alias_that_does_not_say_changes_nothing(self, exited):
        """Somebody's `.bashrc` from a previous release does not set it, and
        then every answer is the one it was before."""
        exited(None)
        assert replay.previous_status() is None
        assert not replay.is_inert('git push')
        assert replay.is_inert('ls -l')

    @pytest.mark.parametrize('raw', ['', 'nonsense', '12x'])
    def test_something_that_is_not_a_number(self, os_environ, raw):
        os_environ[replay.EXIT_ENV] = raw
        assert replay.previous_status() is None


def test_the_loader_hands_the_status_to_the_alias(set_shell):
    """The stub's own `eval` is a command, so it replaces `$?`.

    And the real alias reads `$?` as its first act -- so on the *first*
    correction in a shell, the status it saw was the stub's zero and a command
    that had just failed looked like one that had worked. `bleep` said
    `No bleeps given` the first time and worked every time after, in the same
    shell.

    Reproduced in bash, zsh and fish through the loader, and fixed in all three.

    """
    from thebleep.shells import Bash, Fish, Zsh

    for shell_class in (Bash, Zsh, Fish):
        shell = set_shell(shell_class)
        loader = shell.app_alias_loader('bleep')
        alias = shell.app_alias('bleep')
        name = shell_class.__name__

        # The stub saves it...
        assert ('$?' in loader or '$status' in loader), name
        # ...and hands it over rather than leaving it to be re-read.
        assert '{}='.format(replay.EXIT_ENV) in loader, name
        # ...and the alias prefers what it was handed.
        assert replay.EXIT_ENV in alias, name


def test_every_shell_that_can_report_the_status_does(set_shell):
    """The alias has to capture `$?` as its very first act.

    Anything before it -- reading the alias list, reading the history -- is a
    command of its own and replaces the status being asked about.

    """
    from thebleep.shells import Bash, Fish, Zsh

    for shell_class in (Bash, Zsh, Fish):
        shell = set_shell(shell_class)
        alias = shell.app_alias('bleep')
        assert replay.EXIT_ENV in alias, shell_class.__name__

        # The capture comes before anything else the function does.
        body = alias.split('\n')
        captures = [index for index, line in enumerate(body)
                    if '$?' in line or '$status' in line]
        assert captures, shell_class.__name__
        others = [index for index, line in enumerate(body)
                  if line.strip() and index < captures[0]
                  and not line.strip().startswith(('function', 'bleep',
                                                   '#'))]
        assert not others, '{}: {}'.format(shell_class.__name__, others)


class TestTheProofAndTheReplayAreAboutTheSameThing(object):
    """`is_inert` is a claim about the command; the replay executes more.

    A third-party review put it exactly right: `is_inert()` proves something
    about the command, while `rerun.get_output()` executes *a new shell, its
    startup files, an inherited environment, and then the command*. Those have
    to be the same object for the claim to mean anything, and for a while they
    were not. Every case below was reproduced end to end before it was fixed.

    """

    def test_an_exported_shell_function_is_not_nothing(self, os_environ,
                                                       on_path):
        """`bash -c` imports functions the shell exported.

            deploy() { printf x >> log; return 1; }
            export -f deploy

        `which('deploy')` is `None`, so this was free -- and the function ran a
        second time, unasked. Verified with a real bash and a marker file: `x`
        became `xx`.

        """
        os_environ['BASH_FUNC_deploy%%'] = '() {  printf x >> log\n}'
        assert not replay.is_inert('deploy')
        # And a name that is not one still is.
        assert replay.is_inert('no-such-program-at-all')

    def test_an_exported_read_only_name_is_not_nothing(self, os_environ,
                                                       on_path):
        """A function can replace a conventionally read-only program."""
        os_environ['BASH_FUNC_cat%%'] = '() { printf x >> log; return 1; }'

        assert not replay.is_inert('cat notes.txt')

    def test_the_pre_4_3_spelling_too(self, os_environ, on_path):
        """Which is the shape Shellshock was about, and some builds keep it."""
        os_environ['deploy'] = '() { printf x >> log; }'
        assert not replay.is_inert('deploy')

    @pytest.mark.parametrize('variable', ['BASH_ENV', 'ENV'])
    def test_a_startup_file_makes_opening_the_shell_do_something(
            self, os_environ, on_path, variable):
        """A non-interactive bash sources `$BASH_ENV` before the command it was
        given, so replaying a command that does not exist *at all* still had an
        effect. `ENV` is the POSIX `sh` equivalent."""
        os_environ[variable] = '/tmp/somebodys-startup-file'
        assert not replay.is_inert('no-such-program-at-all')
        assert not replay.is_inert('ls')

    @pytest.mark.parametrize('script', [
        # The dispatcher probe asked `/usr/bin/git` about `satus` while the
        # command that ran was a different git entirely.
        'PATH=/tmp/mine:/usr/bin git satus',
        # No swapping needed: with these set, `git --list-cmds` lists `deploy`;
        # without them it does not, and the probe runs without them.
        'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.deploy'
        ' GIT_CONFIG_VALUE_0=!./deploy.sh git deploy',
        # And the ones that are almost certainly harmless, which pay a question
        # rather than have somebody keep a list of the ones that are not.
        'LC_ALL=C ls',
        'LD_PRELOAD=/tmp/x.so ls',
    ])
    def test_an_assignment_in_front_of_a_command(self, os_environ, on_path,
                                                 script):
        assert not replay.is_inert(script)

    def test_assignments_and_nothing_else_are_still_free(self, on_path):
        """A subshell throws those away, and there is no command for them to
        change the meaning of."""
        assert replay.is_inert('FOO=bar')
        assert replay.is_inert('FOO=bar BAZ=qux')

    @pytest.mark.parametrize('script', ['./ls', '/tmp/mine/ls', 'bin/cat f'])
    def test_a_path_is_not_the_program_that_name_usually_means(
            self, script, on_path):
        """`READ_ONLY` is a judgement about the program conventionally called
        `ls`. `./ls` is a file in this directory that the user has specifically
        said to execute, and its name says nothing about what it does -- one
        written for the occasion re-ran itself and doubled its side effect."""
        assert not replay.is_inert(script)

    def test_a_bare_name_still_is(self, on_path):
        assert replay.is_inert('ls')
        assert replay.is_inert('cat notes.txt')

    @pytest.mark.parametrize('script', [
        'xxd in.bin out.hex',
        'xxd -r patch.hex target.bin',
    ])
    def test_xxd_writes_files(self, script, on_path):
        """It takes an output file as its second operand, and `-r` patches one
        in place -- which is what its own manual page demonstrates. It was on
        `READ_ONLY` until somebody read the manual."""
        assert not replay.is_inert(script)
