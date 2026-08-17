# -*- coding: utf-8 -*-

"""The rule pack is an optimisation, so these tests are about it never
changing an answer: not when a rule is edited, not when the cache is corrupt,
and above all not when a command is dispatched to fewer rules than before.

The last one is checked against the project's own corpus: every `Command(...)`
written with literal arguments anywhere in `tests/rules` is replayed, and any
rule that really matches it has to have survived the pack's prefiltering.
"""

import ast
import marshal
import os
import pytest
import time
from thebleep import rulepack
from thebleep.system import Path
from thebleep.types import Command, Rule

RULES_DIR = Path(__file__).parent.parent.joinpath('thebleep', 'rules')
TESTS_DIR = Path(__file__).parent.joinpath('rules')


@pytest.fixture
def rule_paths():
    return sorted(RULES_DIR.glob('*.py'))


@pytest.fixture
def cache_home(monkeypatch, tmpdir, os_environ):
    os_environ['XDG_CACHE_HOME'] = str(tmpdir)
    return tmpdir


@pytest.fixture
def entries(cache_home, rule_paths):
    return rulepack.entries_for(rule_paths)


def _literal_commands():
    """Every `Command('script', 'output')` written literally in the rule tests.

    Reading the tests instead of importing them keeps this cheap and avoids
    running their fixtures.

    """
    found = []
    for path in sorted(TESTS_DIR.glob('test_*.py')):
        try:
            tree = ast.parse(path.open(encoding='utf-8').read(), str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else \
                getattr(node.func, 'attr', None)
            if name != 'Command' or len(node.args) != 2:
                continue
            try:
                script, output = (ast.literal_eval(node.args[0]),
                                  ast.literal_eval(node.args[1]))
            except (ValueError, TypeError, SyntaxError):
                continue
            if isinstance(script, str) and isinstance(output, str) and script:
                found.append((path.name, script, output))
    return found


CORPUS = _literal_commands()


class TestPack(object):
    def test_builds_an_entry_per_rule(self, entries, rule_paths):
        assert set(entries) == {str(path) for path in rule_paths}
        assert all(entry['code'] for entry in entries.values())

    def test_written_where_the_next_run_finds_it(self, entries, cache_home):
        assert rulepack._cache_path().is_file()

    def test_reused_without_rebuilding(self, entries, rule_paths, mocker):
        build = mocker.patch('thebleep.rulepack._build_entry')
        again = rulepack.entries_for(rule_paths)
        assert not build.called
        assert set(again) == set(entries)

    def test_edited_rule_is_rebuilt(self, cache_home, tmpdir):
        rule = tmpdir.join('made_up_rule.py')
        rule.write('def match(command):\n    return True\n')
        path = Path(str(rule))

        first = rulepack.entries_for([path])[str(path)]
        rule.write('def match(command):\n    return False\n')
        os.utime(str(rule), (0, 0))
        second = rulepack.entries_for([path])[str(path)]

        assert first['code'] != second['code']
        module = rulepack.load_module('made_up_rule', str(path), second['code'])
        assert module.match(Command('anything', '')) is False

    def test_corrupt_pack_is_ignored(self, cache_home, rule_paths):
        rulepack.entries_for(rule_paths)
        with rulepack._cache_path().open('wb') as handle:
            handle.write(b'not a marshalled anything')
        assert rulepack._read_pack() == {}
        assert rulepack.entries_for(rule_paths)

    def test_pack_from_another_interpreter_is_ignored(self, cache_home,
                                                      rule_paths):
        path = rulepack._cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb') as handle:
            marshal.dump({'format': rulepack.FORMAT, 'magic': b'nope',
                          'entries': {'x': {}}}, handle)
        assert rulepack._read_pack() == {}

    def test_unwritable_cache_still_works(self, cache_home, rule_paths,
                                          mocker):
        mocker.patch('thebleep.rulepack._write_pack',
                     side_effect=OSError('read-only'))
        with pytest.raises(OSError):
            rulepack.entries_for(rule_paths)

    def test_clear_removes_the_pack(self, cache_home, rule_paths):
        rulepack.entries_for(rule_paths)
        assert rulepack._cache_path().is_file()
        # A pack left by another interpreter or an older format goes too.
        stale = rulepack._cache_path().parent.joinpath('rules-0-abcdef.pack')
        stale.open('wb').close()
        assert rulepack.clear() == 2
        assert not rulepack._cache_path().is_file()
        assert not stale.is_file()


class TestExecutablesCache(object):
    """The listing of everything on $PATH is remembered between runs, and has
    to stop being remembered the moment a directory changes."""

    @pytest.fixture
    def bin_dir(self, tmpdir, os_environ, cache_home):
        directory = tmpdir.mkdir('bin')
        directory.join('already-here').write('')
        os_environ['PATH'] = str(directory)
        return directory

    def test_lists_what_is_there(self, bin_dir):
        from thebleep import utils
        assert 'already-here' in utils._scan_executables([str(bin_dir)], ())

    def test_second_call_is_served_from_the_cache(self, bin_dir, mocker):
        from thebleep import utils
        utils._scan_executables([str(bin_dir)], ())
        scandir = mocker.patch('os.scandir', return_value=[])
        assert 'already-here' in utils._scan_executables([str(bin_dir)], ())
        assert not scandir.called

    def test_a_new_executable_is_picked_up(self, bin_dir):
        from thebleep import utils
        utils._scan_executables([str(bin_dir)], ())
        # Directory timestamps come from a coarse clock, so an install has to
        # land in a later tick than the read for the mtime to differ. Anything
        # a person can actually do takes longer than this.
        time.sleep(0.02)
        bin_dir.join('just-installed').write('')
        found = utils._scan_executables([str(bin_dir)], ())
        assert 'just-installed' in found

    def test_a_stale_listing_expires(self, bin_dir, mocker):
        from thebleep import utils
        utils._scan_executables([str(bin_dir)], ())
        scandir = mocker.patch('os.scandir', return_value=[])
        mocker.patch('time.time',
                     return_value=time.time()
                     + utils.EXECUTABLES_CACHE_MAX_AGE + 1)
        utils._scan_executables([str(bin_dir)], ())
        assert scandir.called

    def test_entry_points_are_left_out(self, bin_dir):
        from thebleep import utils
        bin_dir.join('bleep').write('')
        found = utils._scan_executables([str(bin_dir)], ('bleep',))
        assert 'bleep' not in found
        assert 'already-here' in found

    def test_directories_are_not_executables(self, bin_dir):
        from thebleep import utils
        bin_dir.mkdir('a-directory')
        assert 'a-directory' not in utils._scan_executables([str(bin_dir)], ())

    def test_missing_directory_is_not_fatal(self, bin_dir):
        from thebleep import utils
        found = utils._scan_executables(
            [str(bin_dir), str(bin_dir.join('nope'))], ())
        assert 'already-here' in found


class TestMetadata(object):
    @pytest.mark.parametrize('source, apps', [
        ("@for_app('git')\ndef match(command):\n    return True\n", ('git',)),
        ("@for_app('apt', 'apt-get')\ndef match(command):\n    return True\n",
         ('apt', 'apt-get')),
        ("@git_support\ndef match(command):\n    return True\n", ('git',)),
        ("@sudo_support\ndef match(command):\n    return True\n", None),
        ("def match(command):\n    return True\n", None),
        ("@for_app(*APPS)\ndef match(command):\n    return True\n", None),
        ("@for_app(SOME_NAME)\ndef match(command):\n    return True\n", None),
    ])
    def test_apps(self, source, apps):
        assert rulepack._extract_metadata(source, 'x.py')['apps'] == apps

    @pytest.mark.parametrize('source, clauses', [
        ("def match(command):\n    return 'no such' in command.output\n",
         ((('no such', False),),)),
        ("def match(command):\n    return 'No Such' in command.output.lower()\n",
         ((('no such', True),),)),
        ("def match(command):\n    return 'a' in command.output and 'b' in command.output\n",
         ((('a', False),), (('b', False),))),
        ("def match(command):\n    return 'a' in command.output or 'b' in command.output\n",
         ((('a', False), ('b', False)),)),
        # One unknown branch of an `or` means nothing is required.
        ("def match(command):\n    return 'a' in command.output or something(command)\n",
         ()),
        # An unknown term in an `and` just contributes no constraint.
        ("def match(command):\n    return something(command) and 'b' in command.output\n",
         ((('b', False),),)),
        # Anything but a lone return is left alone.
        ("def match(command):\n    x = 1\n    return 'a' in command.output\n", ()),
        ("def match(command):\n    if command.script:\n        return 'a' in command.output\n    return False\n",
         ()),
        # A docstring doesn't count as a statement.
        ("def match(command):\n    'doc'\n    return 'a' in command.output\n",
         ((('a', False),),)),
    ])
    def test_output_requirements(self, source, clauses):
        assert rulepack._extract_metadata(source, 'x.py')['output'] == clauses

    @pytest.mark.parametrize('source, key, value', [
        ('enabled_by_default = False\n', 'enabled', False),
        ('enabled_by_default = True\n', 'enabled', True),
        ('enabled_by_default = bool(os.environ)\n', 'enabled', None),
        ('priority = 900\n', 'priority', 900),
        ('requires_output = False\n', 'requires_output', False),
    ])
    def test_module_level_settings(self, source, key, value):
        assert rulepack._extract_metadata(source, 'x.py')[key] == value


class TestDispatch(object):
    @pytest.mark.parametrize('script, apps', [
        ('git branch', {'git'}),
        ('/usr/bin/git branch', {'git'}),
        ('sudo apt-get install vim', {'sudo', 'apt-get'}),
        ('sudo', {'sudo'}),
    ])
    def test_command_apps(self, script, apps):
        assert rulepack.command_apps(Command(script, '')) == apps

    def test_app_rules_are_skipped_for_other_apps(self, entries):
        output = ("git: 'brnch' is not a git command. See 'git --help'.\n"
                  "\nDid you mean this?\n\tbranch\n")
        names = {entry['name']
                 for _, entry in rulepack.candidate_entries(
                     entries, Command('git brnch', output))}
        assert 'git_not_command' in names

        # Every rule that declares an app other than git is gone, whatever
        # those rules happen to be called today.
        other_apps = {entry['name'] for entry in entries.values()
                      if entry['apps'] and 'git' not in entry['apps']}
        assert len(other_apps) > 20
        assert not names.intersection(other_apps)

    def test_output_rules_are_skipped_without_their_output(self, entries):
        # Picked from the real rules rather than named, so the test keeps
        # meaning something as the rules change.
        needy = [entry for entry in entries.values()
                 if entry['output'] and entry['apps'] is None]
        assert needy, 'no rule declares what it needs in the output'
        entry = needy[0]
        needle = entry['output'][0][0][0]

        without = {found['name'] for _, found in rulepack.candidate_entries(
            entries, Command('made-up-command', 'nothing interesting here'))}
        assert entry['name'] not in without

        with_it = {found['name'] for _, found in rulepack.candidate_entries(
            entries, Command('made-up-command', 'x {} x'.format(needle)))}
        assert entry['name'] in with_it

    def test_prefilter_actually_narrows(self, entries):
        command = Command('git brnch', "git: 'brnch' is not a git command.")
        candidates = rulepack.candidate_entries(entries, command)
        assert len(candidates) < len(entries) / 2

    def test_excluded_rules_never_become_candidates(self, entries, settings):
        settings.update(exclude_rules=['git_not_command'])
        names = {entry['name']
                 for _, entry in rulepack.candidate_entries(
                     entries, Command('git brnch', 'is not a git command'))}
        assert 'git_not_command' not in names

    def test_disabled_by_env(self, monkeypatch, os_environ):
        os_environ['THEBLEEP_NO_RULE_PACK'] = 'true'
        assert rulepack.get_rules_for(Command('git brnch', ''), []) is None


@pytest.mark.skipif(not CORPUS, reason='no literal commands found in the tests')
class TestEquivalence(object):
    """Prefiltering must never lose a rule that would have matched."""

    @pytest.fixture
    def all_rules(self, rule_paths):
        loaded = [Rule.from_path(path) for path in rule_paths
                  if path.name != '__init__.py']
        return [rule for rule in loaded if rule and rule.is_enabled]

    def test_corpus_is_substantial(self):
        assert len(CORPUS) > 100

    def test_every_matching_rule_survives_prefiltering(self, entries,
                                                       all_rules):
        misses = []
        for origin, script, output in CORPUS:
            command = Command(script, output)
            candidates = {entry['name']
                          for _, entry in rulepack.candidate_entries(
                              entries, command)}
            for rule in all_rules:
                if rule.name in candidates:
                    continue
                if rule.is_match(command):
                    misses.append('{}: {!r} would have matched {}'.format(
                        origin, script, rule.name))
        assert not misses, '\n'.join(misses[:20])
