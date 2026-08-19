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
