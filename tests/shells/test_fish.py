# -*- coding: utf-8 -*-

import os
import pytest
from pathlib import Path
from thebleep.const import ARGUMENT_PLACEHOLDER
from thebleep.shells import Fish


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestFish(object):
    @pytest.fixture
    def shell(self):
        return Fish()

    @pytest.fixture(autouse=True)
    def probes(self, mocker):
        """What each `fish` probe said, by the words it was asked with.

        Patched at `tool_lines`/`tool_output` rather than at `Popen`, because
        that is where the timeout now lives -- and `fish -ic` reads the user's
        `config.fish`, so a config that waits for something was a correction
        that never came back. It is also where the decoding lives: a non-UTF-8
        locale could put a byte in a function name that strict decoding raised
        on, uncaught, on the hot path of every fish correction.

        """
        self.answers = {
            'functions': ['cd', 'fish_config', 'bleep', 'funced', 'funcsave',
                          'grep', 'history', 'll', 'ls', 'man', 'math', 'popd',
                          'pushd', 'ruby'],
            'alias': ['alias fish_key_reader /usr/bin/fish_key_reader',
                      'alias g git',
                      'alias alias_with_equal_sign=echo',
                      'invalid_alias'],
        }

        def _lines(arguments, *args, **kwargs):
            return self.answers.get(arguments[-1], [])

        mocker.patch('thebleep.shells.fish.tool_lines', side_effect=_lines)
        return mocker.patch('thebleep.shells.fish.tool_output',
                            return_value='')

    @pytest.mark.parametrize('key, value', [
        ('TB_OVERRIDDEN_ALIASES', 'cut,git,sed'),  # legacy
        ('THEBLEEP_OVERRIDDEN_ALIASES', 'cut,git,sed'),
        ('THEBLEEP_OVERRIDDEN_ALIASES', 'cut, git, sed'),
        ('THEBLEEP_OVERRIDDEN_ALIASES', ' cut,\tgit,sed\n'),
        ('THEBLEEP_OVERRIDDEN_ALIASES', '\ncut,\n\ngit,\tsed\r')])
    def test_get_overridden_aliases(self, shell, os_environ, key, value):
        os_environ[key] = value
        overridden = shell._get_overridden_aliases()
        assert set(overridden) == {'cd', 'cut', 'git', 'grep',
                                   'ls', 'man', 'open', 'sed'}

    @pytest.mark.parametrize('before, after', [
        ('cd', 'cd'),
        ('pwd', 'pwd'),
        ('bleep', 'fish -ic "bleep"'),
        ('find', 'find'),
        ('funced', 'fish -ic "funced"'),
        ('grep', 'grep'),
        ('awk', 'awk'),
        ('math "2 + 2"', r'fish -ic "math \"2 + 2\""'),
        ('man', 'man'),
        ('open', 'open'),
        ('vim', 'vim'),
        ('ll', 'fish -ic "ll"'),
        ('ls', 'ls'),
        ('g', 'git')])
    def test_from_shell(self, before, after, shell):
        assert shell.from_shell(before) == after

    def test_to_shell(self, shell):
        assert shell.to_shell('pwd') == 'pwd'

    def test_and_(self, shell):
        assert shell.and_('foo', 'bar') == 'foo; and bar'

    def test_or_(self, shell):
        assert shell.or_('foo', 'bar') == 'foo; or bar'

    def test_get_aliases(self, shell):
        assert shell.get_aliases() == {'fish_config': 'fish_config',
                                       'bleep': 'bleep',
                                       'funced': 'funced',
                                       'funcsave': 'funcsave',
                                       'history': 'history',
                                       'll': 'll',
                                       'math': 'math',
                                       'popd': 'popd',
                                       'pushd': 'pushd',
                                       'ruby': 'ruby',
                                       'g': 'git',
                                       'fish_key_reader': '/usr/bin/fish_key_reader',
                                       'alias_with_equal_sign': 'echo'}

    def test_get_aliases_asks_again_when_fish_changes(self, shell):
        """Two `functions` and no aliases, after the first answer."""
        self.answers = {'functions': ['func1', 'func2'], 'alias': []}
        assert shell.get_aliases() == {'func1': 'func1', 'func2': 'func2'}

    def test_get_aliases_includes_current_session_aliases(
            self, shell, os_environ):
        """The child fish cannot see an alias defined after config loading."""
        os_environ['TB_SHELL_ALIASES'] = "alias ll 'ls -l'"
        assert shell.get_aliases()['ll'] == "'ls -l'"

    def test_app_alias(self, shell):
        assert 'function bleep' in shell.app_alias('bleep')
        assert 'function BLEEP' in shell.app_alias('BLEEP')
        assert 'thebleep' in shell.app_alias('bleep')
        assert 'TB_SHELL_ALIASES="$shell_aliases"' in shell.app_alias('bleep')
        assert 'TB_SHELL=fish' in shell.app_alias('bleep')
        assert ('TB_ALIAS=bleep TB_CAN_EDIT=1 TB_EXIT=$tb_exit'
                ' TB_SHELL_ALIASES="$shell_aliases" thebleep'
                in shell.app_alias('bleep'))
        assert ARGUMENT_PLACEHOLDER in shell.app_alias('bleep')

    def test_app_alias_loader(self, shell):
        loader = shell.app_alias_loader('bleep')
        assert 'function bleep' in loader
        assert 'functions -e bleep' in loader
        assert 'thebleep --alias bleep | source' in loader

    def test_instant_mode_is_supported(self, shell):
        assert shell.supports_instant_mode()

    def test_instant_mode_starts_the_logger(self, shell, os_environ,
                                            monkeypatch):
        monkeypatch.setattr(
            'thebleep.shells.fish.instant_log_path',
            lambda: '/tmp/fish capture')
        alias = shell.instant_mode_alias('bleep')
        assert 'set -gx THEBLEEP_INSTANT_MODE True' in alias
        assert "set -gx THEBLEEP_OUTPUT_LOG '/tmp/fish capture'" in alias
        assert 'env SHELL=fish' in alias
        assert '--shell-logger' in alias
        assert 'fish_exit' in alias

    def test_instant_mode_marks_the_fish_prompt(self, shell, os_environ):
        os_environ['THEBLEEP_INSTANT_MODE'] = 'true'
        alias = shell.instant_mode_alias('bleep')
        assert 'functions --copy fish_prompt' in alias
        assert 'function fish_prompt' in alias
        assert 'printf' in alias
        assert 'function bleep' in alias

    def test_app_alias_alter_history(self, settings, shell):
        settings.alter_history = True
        assert (
            'builtin history delete --exact --case-sensitive -- $broken_command\n'
            in shell.app_alias('BLEEP')
        )
        assert 'builtin history merge\n' in shell.app_alias('BLEEP')
        settings.alter_history = False
        assert 'builtin history delete' not in shell.app_alias('BLEEP')
        assert 'builtin history merge' not in shell.app_alias('BLEEP')

    def test_inline_binding_only_edits_commandline(self, shell):
        binding = shell.inline_binding()
        assert 'bind \\e\\e __thebleep_inline' in binding
        assert 'alias | string collect' in binding
        assert 'TB_SHELL_ALIASES="$shell_aliases"' in binding
        assert '--inline --command (commandline)' in binding
        assert 'commandline --replace -- $fixed' in binding
        assert 'eval' not in binding

    @pytest.mark.parametrize('env, history_file_name', [
        ({}, '~/.local/share/fish/fish_history'),
        ({'XDG_DATA_HOME': '/xdg/data'}, '/xdg/data/fish/fish_history'),
        ({'fish_history': 'work'}, '~/.local/share/fish/work_history')])
    def test_get_history_file_name(self, shell, os_environ, env,
                                   history_file_name):
        os_environ.update(env)
        # Compare as paths, the shell joins them with the native separator.
        assert (Path(shell._get_history_file_name())
                == Path(os.path.expanduser(history_file_name)))

    def test_get_history_file_name_legacy(self, shell, isfile):
        legacy = os.path.expanduser('~/.config/fish/fish_history')
        isfile.side_effect = lambda path: path == legacy
        assert shell._get_history_file_name() == legacy

    def test_get_history(self, history_lines, shell):
        history_lines(['- cmd: ls', '  when: 1432613911',
                       '- cmd: rm', '  when: 1432613916'])
        assert list(shell.get_history()) == ['ls', 'rm']

    @pytest.mark.parametrize('entry, entry_utf8', [
        ('ls', '- cmd: ls\n   when: 1430707243\n'),
        (u'echo café', '- cmd: echo café\n   when: 1430707243\n')])
    def test_put_to_history(self, entry, entry_utf8, builtins_open, mocker, shell):
        mocker.patch('thebleep.shells.fish.time', return_value=1430707243.3517463)
        shell.put_to_history(entry)
        builtins_open.return_value.__enter__.return_value. \
            write.assert_called_once_with(entry_utf8)

    def test_how_to_configure(self, shell, config_exists):
        config_exists.return_value = True
        assert shell.how_to_configure().can_configure_automatically

    def test_how_to_configure_when_config_not_found(self, shell,
                                                    config_exists):
        config_exists.return_value = False
        assert not shell.how_to_configure().can_configure_automatically

    def test_get_version(self, shell, probes):
        probes.return_value = 'fish, version 3.5.9'
        assert shell._get_version() == '3.5.9'
        assert probes.call_args[0][0] == ['fish', '--version']

    def test_a_probe_that_answers_nothing(self, shell, probes):
        """An empty answer used to be an `IndexError` off the end of an empty
        `split()`, and a fish that is not there an uncaught `OSError`."""
        probes.return_value = ''
        assert shell._get_version() == ''
        assert shell.info() == 'Fish Shell'


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestAmbient(object):
    @pytest.fixture
    def shell(self):
        return Fish()

    def test_return_is_bound_in_both_keymaps(self, shell):
        binding = shell.ambient_binding()
        assert 'bind \\r __thebleep_ambient_execute' in binding
        assert 'bind -M insert \\r __thebleep_ambient_execute' in binding
        assert 'commandline -f execute' in binding

    def test_only_an_unknown_first_word_asks(self, shell):
        binding = shell.ambient_binding()
        assert 'not type -q -- "$first"' in binding
        assert '--inline --command "$buffer"' in binding
        assert 'commandline -r -- $fixed' in binding

    def test_the_word_test_is_one_fish_string(self, shell):
        """A quote inside a single-quoted fish string has to be escaped, or
        the pattern ends there and the rest is shell syntax."""
        expected = "string match -qr '[/=$\\'\"`]' -- \"$first\""
        assert expected in shell.ambient_binding()


@pytest.mark.usefixtures('isfile', 'no_memoize', 'no_cache')
class TestInstantModeMarks(object):
    @pytest.fixture
    def shell(self):
        return Fish()

    def test_fish_3_gets_the_marks_fish_4_emits_itself(
            self, shell, os_environ):
        os_environ['THEBLEEP_INSTANT_MODE'] = 'true'
        alias = shell.instant_mode_alias('bleep')
        assert 'if test (string split . -- $FISH_VERSION)[1] -lt 4' in alias
        assert '--on-event fish_preexec' in alias
        assert "printf '\\e]133;C\\a'" in alias
        assert "printf '\\e]133;D;%s\\a' $status" in alias
        assert '--on-event fish_prompt' in alias
