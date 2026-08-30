# -*- coding: utf-8 -*-

import pytest
from tests.utils import Rule, CorrectedCommand
from thebleep import corrector, const
from thebleep.types import Command
from thebleep.corrector import get_corrected_commands, organize_commands


@pytest.fixture
def glob(mocker):
    """Stands in for the rule files found on disk.

    `_rule_files` hands back each path with the size and mtime the directory
    listing already told it, so the rule pack does not ask the filesystem for all
    of them a second time. Tests here care only about the paths, so the fixture
    still takes those and fills the rest in.

    """
    results = {}
    mocker.patch('thebleep.corrector._rule_files',
                 new_callable=lambda: lambda *_: results.pop('value', {}))
    return lambda paths: results.update(
        {'value': {path: (0, 0) for path in paths}})


class TestGetRules(object):
    @pytest.fixture(autouse=True)
    def load_source(self, monkeypatch):
        monkeypatch.setattr('thebleep.types.load_source',
                            lambda x, _: Rule(x))

    def _compare_names(self, rules, names):
        assert {r.name for r in rules} == set(names)

    @pytest.mark.parametrize('paths, conf_rules, exclude_rules, loaded_rules', [
        (['git.py', 'bash.py'], const.DEFAULT_RULES, [], ['git', 'bash']),
        (['git.py', 'bash.py'], ['git'], [], ['git']),
        (['git.py', 'bash.py'], const.DEFAULT_RULES, ['git'], ['bash']),
        (['git.py', 'bash.py'], ['git'], ['git'], [])])
    def test_get_rules(self, glob, settings, paths, conf_rules, exclude_rules,
                       loaded_rules):
        glob(paths)
        settings.update(rules=conf_rules,
                        priority={},
                        exclude_rules=exclude_rules)
        rules = corrector.get_rules()
        self._compare_names(rules, loaded_rules)


def test_get_rules_rule_exception(mocker, glob):
    load_source = mocker.patch('thebleep.types.load_source',
                               side_effect=ImportError("No module named foo..."))
    glob(['git.py'])
    assert not corrector.get_rules()
    load_source.assert_called_once_with('git', 'git.py')


def test_get_corrected_commands(mocker):
    command = Command('test', 'test')
    rules = [Rule(match=lambda _: False),
             Rule(match=lambda _: True,
                  get_new_command=lambda x: x.script + '!', priority=100),
             Rule(match=lambda _: True,
                  get_new_command=lambda x: [x.script + '@', x.script + ';'],
                  priority=60)]
    mocker.patch('thebleep.corrector.get_rules', return_value=rules)
    assert ([cmd.script for cmd in get_corrected_commands(command)]
            == ['test!', 'test@', 'test;'])


def test_learned_correction_is_offered_before_rules(mocker, settings, tmpdir,
                                                    monkeypatch):
    from thebleep import learning
    from thebleep.system import Path

    settings.user_dir = Path(str(tmpdir))
    monkeypatch.chdir(str(tmpdir))
    assert learning.remember_pending(
        'corpctl deply payments', 'corpctl deploy payments',
        cwd=str(tmpdir), shell_name='generic')
    assert learning.learn_last() is not None
    mocker.patch('thebleep.corrector.get_rules', return_value=[
        Rule(match=lambda _: True,
             get_new_command=lambda _: 'corpctl deploy all',
             priority=100)])

    commands = get_corrected_commands(
        Command('corpctl deply payments', 'unrelated output'))

    assert [command.script for command in commands] == [
        'corpctl deploy payments', 'corpctl deploy all']


def test_organize_commands():
    """Ensures that the function removes duplicates and sorts commands."""
    commands = [CorrectedCommand('ls'), CorrectedCommand('ls -la', priority=9000),
                CorrectedCommand('ls -lh', priority=100),
                CorrectedCommand(u'echo café', priority=200),
                CorrectedCommand('ls -lh', priority=9999)]
    assert list(organize_commands(iter(commands))) \
        == [CorrectedCommand('ls'), CorrectedCommand('ls -lh', priority=100),
            CorrectedCommand(u'echo café', priority=200),
            CorrectedCommand('ls -la', priority=9000)]


class TestCorrectionsBehindAWrapper(object):
    """Every rule gets the command underneath, and the wrapper comes back."""

    OUTPUT = ("git: 'chekout' is not a git command. See 'git --help'.\n\n"
              "The most similar command is\n\tcheckout\n")

    def _corrections(self, script):
        from thebleep.corrector import get_corrected_commands
        from thebleep.types import Command

        return [corrected.script for corrected
                in get_corrected_commands(Command(script, self.OUTPUT))]

    @pytest.mark.parametrize('script, corrected', [
        ('git chekout master', 'git checkout master'),
        ('sudo git chekout master', 'sudo git checkout master'),
        ('sudo -u www-data git chekout master',
         'sudo -u www-data git checkout master'),
        ('nice -n 10 git chekout master', 'nice -n 10 git checkout master'),
        ('env FOO=bar git chekout master', 'env FOO=bar git checkout master'),
        ('nohup git chekout master', 'nohup git checkout master'),
        ('doas git chekout master', 'doas git checkout master'),
        ('command git chekout master', 'command git checkout master'),
        ('setsid -f sudo -u root git chekout master',
         'setsid -f sudo -u root git checkout master'),
        ('echo ready && git chekout master',
         'echo ready && git checkout master'),
        ('echo ready | sudo env DEBUG=1 git chekout master >git.log',
         'echo ready | sudo env DEBUG=1 git checkout master >git.log'),
        ('sudo env DEBUG=1 git chekout master >git.log',
         'sudo env DEBUG=1 git checkout master >git.log'),
    ])
    def test_the_wrapper_comes_back_with_the_correction(self, script,
                                                        corrected):
        assert corrected in self._corrections(script)

    @pytest.mark.parametrize('script', [
        'sudo -i git chekout master',
        'sudo -e git chekout master',
        'command -v git chekout master',
    ])
    def test_a_wrapper_that_runs_something_else_is_left_alone(self, script):
        """These do not run the command, so it is not the one to correct."""
        assert 'git checkout master' not in ' '.join(self._corrections(script))

    def test_repeated_output_word_in_compound_command_is_ambiguous(self):
        script = 'git chekout master && git chekout other'

        assert self._corrections(script) == []


class TestSuggestionsWorthMaking(object):
    """Somebody's own command handed back is not a correction."""

    def _organized(self, scripts, script, side_effect=None):
        return [corrected.script for corrected in organize_commands(
            iter([CorrectedCommand(one, side_effect, 100) for one in scripts]),
            script)]

    def test_a_suggestion_identical_to_the_command_is_dropped(self):
        assert self._organized(['git status'], 'git status') == []

    def test_whitespace_does_not_make_it_a_different_command(self):
        assert self._organized(['git status '], '  git status') == []

    def test_an_empty_suggestion_is_dropped(self):
        assert self._organized(['', '   '], 'git status') == []

    def test_the_others_are_kept(self):
        assert self._organized(['git status', 'git stash'], 'git status') == \
            ['git stash']

    def test_an_identical_one_with_a_side_effect_stays(self):
        """There the command being unchanged is the point of the suggestion."""
        assert self._organized(['ssh host'], 'ssh host',
                               side_effect=lambda *_: None) == ['ssh host']

    def test_nothing_left_is_nothing_offered(self):
        assert self._organized(['git status'], 'git status') == []
