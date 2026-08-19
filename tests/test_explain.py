# -*- coding: utf-8 -*-

"""Why a suggestion is being made.

Everything reported has to be a fact about the rule rather than a description of
it: its name, where its file came from, what it declares about itself, and the
conditions its own `match` states. Nothing here may be invented from reading a
rule's body, which is what these are mostly checking.

"""

import os
import pytest
from thebleep import explain
from thebleep.types import Command, CorrectedCommand, Rule


def _rule(name='a_rule', path=None, requires_output=True, side_effect=None):
    return Rule(name, lambda command: True, lambda command: 'fixed',
                True, side_effect, 1000, requires_output, path)


def _suggestion(script='fixed', rule=None, side_effect=None):
    return CorrectedCommand(script, side_effect, 1000, rule=rule)


def _as_dict(lines):
    return dict(lines)


class TestWhereTheRuleCameFrom(object):
    def test_a_bundled_rule(self):
        path = os.path.join(os.path.dirname(explain.__file__), 'rules',
                            'git_not_command.py')
        described = _as_dict(explain.describe(
            _suggestion(rule=_rule('git_not_command', path))))
        assert described['rule'] == 'git_not_command (bundled)'

    def test_a_rule_of_your_own(self, tmpdir):
        path = str(tmpdir.mkdir('rules').join('mine.py'))
        described = _as_dict(explain.describe(
            _suggestion(rule=_rule('mine', path))))
        assert described['rule'] == 'mine (one of your own)'

    def test_a_rule_from_a_package(self, tmpdir):
        path = str(tmpdir.mkdir('thebleep_contrib_stuff').mkdir('rules')
                   .join('theirs.py'))
        described = _as_dict(explain.describe(
            _suggestion(rule=_rule('theirs', path))))
        assert 'thebleep_contrib_stuff' in described['rule']

    def test_a_suggestion_with_no_rule_behind_it_says_so(self):
        described = _as_dict(explain.describe(_suggestion()))
        assert 'unknown' in described['rule']


class TestWhatItMatched(object):
    """Read out of the rule's own syntax tree, the same way dispatch reads it."""

    def _rule_file(self, tmpdir, source):
        path = tmpdir.mkdir('rules').join('probe.py')
        path.write_text(source, 'utf-8')
        return _rule('probe', str(path))

    def test_the_app_a_rule_is_about(self, tmpdir):
        rule = self._rule_file(tmpdir, u'''
from thebleep.utils import for_app


@for_app('git')
def match(command):
    return True


def get_new_command(command):
    return 'fixed'
''')
        described = _as_dict(explain.describe(_suggestion(rule=rule)))
        assert described['matched'] == 'git, whatever it printed'

    def test_the_text_it_requires_in_the_output(self, tmpdir):
        rule = self._rule_file(tmpdir, u'''
from thebleep.utils import for_app


@for_app('git')
def match(command):
    return 'is not a git command' in command.output


def get_new_command(command):
    return 'fixed'
''')
        described = _as_dict(explain.describe(_suggestion(rule=rule)))
        assert described['matched'] == \
            'git, and output containing "is not a git command"'

    def test_it_quotes_the_alternative_that_is_actually_there(self, tmpdir):
        """A clause is alternatives; the one in the output is the true one."""
        rule = self._rule_file(tmpdir, u'''
def match(command):
    return 'first thing' in command.output or 'second thing' in command.output


def get_new_command(command):
    return 'fixed'
''')
        command = Command('x', 'it said the second thing happened')
        described = _as_dict(explain.describe(_suggestion(rule=rule), command))
        assert described['matched'] == 'output containing "second thing"'

    def test_a_long_message_is_shortened(self, tmpdir):
        rule = self._rule_file(tmpdir, u'''
def match(command):
    return {!r} in command.output


def get_new_command(command):
    return 'fixed'
'''.format('a very long message ' * 10))
        described = _as_dict(explain.describe(_suggestion(rule=rule)))
        assert len(described['matched']) < 100
        assert u'…' in described['matched']

    def test_a_rule_that_says_nothing_about_itself(self, tmpdir):
        rule = self._rule_file(tmpdir, u'''
import re

PATTERN = re.compile('x')


def match(command):
    return bool(PATTERN.search(command.script))


def get_new_command(command):
    return 'fixed'
''')
        described = _as_dict(explain.describe(_suggestion(rule=rule)))
        assert described['matched'] == \
            'a condition this rule works out for itself'


class TestWhatItRead(object):
    def test_a_rule_that_needs_the_output(self):
        described = _as_dict(explain.describe(
            _suggestion(rule=_rule(requires_output=True))))
        assert described['read'] == 'what your command printed'

    def test_a_rule_that_does_not(self):
        described = _as_dict(explain.describe(
            _suggestion(rule=_rule(requires_output=False))))
        assert 'not its output' in described['read']

    def test_when_the_output_was_not_available(self):
        """Replay was refused, so there was nothing to read."""
        described = _as_dict(explain.describe(
            _suggestion(rule=_rule(requires_output=True)),
            Command('x', None)))
        assert 'not available' in described['read']


class TestWhatAcceptingItDoes(object):
    def test_a_side_effect_is_called_out(self):
        described = _as_dict(explain.describe(
            _suggestion(rule=_rule(), side_effect=lambda *_: None)))
        assert 'besides run the command' in described['side effect']

    @pytest.mark.parametrize('script', ['sudo rm -r x', 'doas rm -r x',
                                        '/usr/bin/sudo rm -r x'])
    def test_running_as_somebody_else_is_called_out(self, script):
        described = _as_dict(explain.describe(
            _suggestion(script, rule=_rule())))
        assert 'another user' in described['runs as']

    def test_an_ordinary_correction_says_neither(self):
        described = _as_dict(explain.describe(
            _suggestion('git status', rule=_rule())))
        assert 'side effect' not in described
        assert 'runs as' not in described


class TestInTheUi(object):
    @pytest.fixture(autouse=True)
    def is_interactive(self, mocker):
        return mocker.patch('thebleep.ui.is_interactive', return_value=True)

    @pytest.fixture
    def patch_get_key(self, monkeypatch):
        def patch(vals):
            vals = iter(vals)
            monkeypatch.setattr('thebleep.ui.get_key', lambda: next(vals))

        return patch

    @pytest.fixture
    def commands(self):
        return [_suggestion('ls', _rule('a_rule')),
                _suggestion('cd', _rule('another_rule'))]

    @pytest.mark.usefixtures('no_colors')
    def test_the_question_mark_asks(self, capsys, patch_get_key, commands):
        from thebleep import ui, const

        patch_get_key([const.KEY_QUESTION, '\n'])
        ui.select_command(iter(commands))
        assert 'a_rule' in capsys.readouterr()[1]

    @pytest.mark.usefixtures('no_colors')
    def test_asking_once_keeps_answering(self, capsys, patch_get_key,
                                         commands):
        """Walking the suggestions after asking why is asking about each."""
        from thebleep import ui, const

        patch_get_key([const.KEY_QUESTION, const.KEY_DOWN, '\n'])
        ui.select_command(iter(commands))
        printed = capsys.readouterr()[1]
        assert 'a_rule' in printed
        assert 'another_rule' in printed

    @pytest.mark.usefixtures('no_colors')
    def test_not_asked_is_not_told(self, capsys, patch_get_key, commands):
        from thebleep import ui

        patch_get_key(['\n'])
        ui.select_command(iter(commands))
        assert 'a_rule' not in capsys.readouterr()[1]

    @pytest.mark.usefixtures('no_colors')
    def test_the_setting_explains_from_the_start(self, capsys, patch_get_key,
                                                 commands, settings):
        from thebleep import ui

        settings.explain = True
        patch_get_key(['\n'])
        ui.select_command(iter(commands))
        assert 'a_rule' in capsys.readouterr()[1]

    @pytest.mark.usefixtures('no_colors')
    def test_it_explains_without_a_question_too(self, capsys, commands,
                                                settings):
        """`--explain --yes` still says why, it just does not ask."""
        from thebleep import ui

        settings.explain = True
        settings.require_confirmation = False
        ui.select_command(iter(commands))
        assert 'a_rule' in capsys.readouterr()[1]
