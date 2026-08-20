# -*- coding: utf-8 -*-

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
