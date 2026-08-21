# -*- coding: utf-8 -*-

import os
import pytest
from thebleep.shells import Generic


class TestGeneric(object):
    @pytest.fixture
    def shell(self):
        return Generic()

    def test_from_shell(self, shell):
        assert shell.from_shell('pwd') == 'pwd'

    def test_to_shell(self, shell):
        assert shell.to_shell('pwd') == 'pwd'

    def test_and_(self, shell):
        assert shell.and_('ls', 'cd') == 'ls && cd'

    def test_or_(self, shell):
        assert shell.or_('ls', 'cd') == 'ls || cd'

    def test_get_aliases(self, shell):
        assert shell.get_aliases() == {}

    def test_app_alias(self, shell):
        assert 'alias bleep' in shell.app_alias('bleep')
        assert 'alias BLEEP' in shell.app_alias('BLEEP')
        assert 'thebleep' in shell.app_alias('bleep')
        assert 'TB_ALIAS=bleep thebleep' in shell.app_alias('bleep')

    def test_app_alias_loader(self, shell):
        loader = shell.app_alias_loader('BLEEP')
        assert 'BLEEP() {' in loader
        assert 'thebleep --alias BLEEP' in loader

    def test_get_history(self, history_lines, shell):
        history_lines(['ls', 'rm'])
        # We don't know what to do in generic shell with history lines,
        # so just ignore them:
        assert list(shell.get_history()) == []

    def test_split_command(self, shell):
        assert shell.split_command('ls') == ['ls']
        assert shell.split_command(u'echo café') == [u'echo', u'café']

    def test_how_to_configure(self, shell):
        assert shell.how_to_configure() is None

    @pytest.mark.parametrize('side_effect, expected_info, warn', [
        ([u'3.5.9'], u'Generic Shell 3.5.9', False),
        ([OSError], u'Generic Shell', True),
    ])
    def test_info(self, side_effect, expected_info, warn, shell, mocker):
        warn_mock = mocker.patch('thebleep.shells.generic.warn')
        shell._get_version = mocker.Mock(side_effect=side_effect)
        assert shell.info() == expected_info
        assert warn_mock.called is warn
        assert shell._get_version.called


class TestMakingADirectory(object):
    """Nushell's `mkdir` is not `/bin/mkdir`, and three of the commonest
    corrections were emitting code it refuses to parse."""

    def test_a_posix_shell_says_minus_p(self):
        from thebleep.shells import Bash, Fish, Generic, Zsh

        for shell_class in (Generic, Bash, Zsh, Fish):
            assert shell_class().mkdir_command() == 'mkdir -p'
            assert shell_class().mkdir_p('a b') == "mkdir -p 'a b'"

    def test_nushell_does_not(self):
        """Verified against nu 0.108: `mkdir -p x` is a parse error there, and
        `mkdir a/b/c` makes the parents anyway."""
        from thebleep.shells import Nushell

        assert Nushell().mkdir_command() == 'mkdir'
        assert '-p' not in Nushell().mkdir_p('somewhere')

    def test_every_rule_that_makes_a_directory_asks_the_shell(self,
                                                              source_root):
        """A hard-coded `mkdir -p` in a rule is the bug this fixed, so the
        absence of one is what is asserted."""
        import ast
        import io
        import os

        rules = source_root.joinpath('thebleep', 'rules')
        offenders = []
        for name in sorted(os.listdir(str(rules))):
            if not name.endswith('.py'):
                continue

            with io.open(str(rules.joinpath(name)), encoding='utf-8') as f:
                source = f.read()

            # Only what runs. Several of these rules quote the old, broken
            # suggestion in their docstring to explain what went wrong, and a
            # check that could not tell prose from code would forbid that.
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Constant):
                    continue
                if not isinstance(node.value, str):
                    continue
                if 'mkdir -p' not in node.value:
                    continue
                if node.value.strip().startswith(('`', '$')) \
                        or '\n' in node.value:
                    # A docstring or a multi-line example.
                    continue
                offenders.append('{}:{}'.format(name, node.lineno))

        assert not offenders, offenders


class TestSplittingACommandThatContainsTheSentinel(object):
    """`split_command` swaps `\\ ` for a marker while `shlex` does the work.

    The marker used to be `??`, which is two characters anybody can type. A
    command containing one came back out with an escaped space where its
    question marks had been -- so `script_parts` was not the command any more,
    and every rule that reads it was reading something the user never wrote.

    """

    @pytest.fixture
    def shell(self):
        return Generic()

    @pytest.mark.parametrize('command, parts', [
        ("grep '??' notes.txt", ['grep', '??', 'notes.txt']),
        ("curl 'https://x/?a=1??b=2'", ['curl', 'https://x/?a=1??b=2']),
        ('ls ??', ['ls', '??']),
        # And the case the marker exists for still works.
        ('ls a\\ b', ['ls', 'a\\ b']),
        ('cp a\\ b c\\ d', ['cp', 'a\\ b', 'c\\ d']),
    ])
    def test_the_command_survives(self, shell, command, parts):
        assert shell.split_command(command) == parts

    def test_the_marker_is_not_something_anybody_types(self, shell):
        from thebleep.shells.generic import Generic

        assert Generic.ESCAPED_SPACE not in ' '.join(chr(c) for c in range(128))


class TestReadingTheHistory(object):
    """`no_command` asks for history on the busiest path there is.

    It used to `readlines()` the whole file and then slice off the last ten
    entries. Fifty thousand lines is nothing; somebody with `HISTSIZE` unset and
    years of shell has a file measured in megabytes, and all of it was read and
    decoded to look at ten commands.

    """

    @pytest.fixture
    def shell(self, tmpdir):
        history = tmpdir.join('history')

        class Recorded(Generic):
            def _get_history_file_name(self):
                return str(history)

            def _script_from_history(self, line):
                return line

        Recorded.history = history
        return Recorded()

    def _write(self, shell, count):
        shell.history.write('\n'.join(
            'command number {}'.format(n) for n in range(count)) + '\n')

    def test_it_reads_the_end(self, shell, settings):
        settings.history_limit = 10
        self._write(shell, 50000)
        got = shell.get_history()
        assert len(got) == 10
        assert got[-1].strip() == 'command number 49999'
        assert got[0].strip() == 'command number 49990'

    def test_a_file_smaller_than_the_tail(self, shell, settings):
        settings.history_limit = 10
        self._write(shell, 3)
        assert [line.strip() for line in shell.get_history()] == [
            'command number 0', 'command number 1', 'command number 2']

    def test_no_limit_reads_everything(self, shell, settings):
        settings.history_limit = None
        self._write(shell, 100)
        assert len(shell.get_history()) == 100

    def test_lines_long_enough_to_empty_the_tail(
            self, shell, settings, monkeypatch):
        """More entries asked for than the tail held: pay for the whole file
        rather than answer short."""
        monkeypatch.setattr(Generic, 'HISTORY_TAIL', 64)
        settings.history_limit = 5
        shell.history.write('\n'.join('x' * 100 for _ in range(20)) + '\n')
        assert len(shell.get_history()) == 5

    def test_a_missing_file_is_no_history(self, shell, settings, tmpdir):
        settings.history_limit = 10
        assert shell.get_history() == []


class TestReplayingInTheRightShell(object):
    """`Popen(shell=True)` is the platform's shell, not the user's."""

    @pytest.fixture
    def shell(self):
        return Generic()

    def test_a_shell_it_does_not_recognise_says_nothing(self, shell):
        """And then the replay goes through what it always went through."""
        assert shell.replay_argv('echo hi') is None

    @pytest.mark.parametrize('name, argv', [
        ('Bash', ['bash', '-c', 'echo hi']),
        ('Zsh', ['zsh', '-c', 'echo hi']),
        ('Fish', ['fish', '-c', 'echo hi']),
        ('Tcsh', ['tcsh', '-c', 'echo hi']),
        ('Nushell', ['nu', '--commands', 'echo hi']),
    ])
    @pytest.mark.skipif(os.name == 'nt', reason='POSIX drivers stand aside there')
    def test_each_shell_names_itself(self, name, argv):
        from thebleep import shells

        assert getattr(shells, name)().replay_argv('echo hi') == argv

    @pytest.mark.parametrize('name', ['Bash', 'Zsh', 'Fish', 'Tcsh'])
    def test_a_posix_shell_on_windows_stands_aside(self, name, monkeypatch):
        """Git Bash, MSYS and WSL each have their own PATH and their own
        /usr/bin, so starting one to reproduce a command typed in the other
        reproduces a different machine."""
        from thebleep import shells
        from thebleep.shells import generic

        monkeypatch.setattr(generic.os, 'name', 'nt')
        assert getattr(shells, name)().replay_argv('echo hi') is None


class TestWhatInfoIsAllowedToSay(object):
    """`--version` prints one line, and `info()` is that line.

    4.0.3 shipped with `[WARN] Could not determine Generic Shell version` in
    front of every `thebleep --version` on a machine whose shell was not
    recognised. Nothing had failed: `Generic` is the driver for exactly that
    case, its `_get_version` has no program to ask, and a warning added for the
    real drivers -- where an empty answer means the shell would not start -- read
    that "no version exists" as "the probe failed".

    A regression nobody would notice in a test that only checked the version
    line, which is what the tests for this did.

    """

    @pytest.fixture
    def shell(self):
        return Generic()

    def test_the_fallback_shell_complains_about_nothing(self, shell, capsys):
        assert shell.info() == 'Generic Shell'
        assert capsys.readouterr()[1] == ''

    def test_a_real_driver_with_nothing_to_say_still_says_so(
            self, capsys, mocker):
        """The case the warning was added for: a driver that has a shell to
        ask, asked it, and got nothing -- which is what a shell that is not
        there or will not start looks like."""
        from thebleep.shells import Bash

        mocker.patch.object(Bash, '_get_version', return_value='')
        assert Bash().info() == 'Bash'
        assert 'Could not determine' in capsys.readouterr()[1]

    @pytest.mark.parametrize('name', [
        'Generic', 'Bash', 'Zsh', 'Fish', 'Tcsh', 'Nushell', 'Powershell',
    ])
    def test_no_driver_warns_when_it_has_a_version(self, name, capsys, mocker):
        from thebleep import shells

        driver = getattr(shells, name)
        mocker.patch.object(driver, '_get_version', return_value='1.2.3')
        assert driver().info().endswith('1.2.3')
        assert capsys.readouterr()[1] == ''
