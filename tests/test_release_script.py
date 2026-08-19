# -*- coding: utf-8 -*-

"""`release.py` before it writes anything.

Preparing a release used to begin by putting the new version into `setup.py`, the
README badge and the CHANGELOG heading, and only then find out whether this
interpreter had `pytest` in it. So running it with the wrong Python left a
half-prepared release in the tree, a date on a version that was never released,
and a `git checkout` to work out from the traceback.

What is checked here is the order, and that a release attempt which does not
finish leaves nothing behind. None of it runs the gates or builds anything: the
script's own subprocesses are stood in for, and `HERE` is pointed at a copy of
the three files, so a test cannot touch the real ones.

"""

import io
import os
import shutil
import sys
import pytest

VERSIONED = ('setup.py', 'README.md', 'CHANGELOG.md')


@pytest.fixture(autouse=True)
def the_real_files_are_not_touched(source_root):
    """Every test here works on a copy; this is what says so.

    It used to be a test asserting the repository stood at `4.0.0 -- unreleased`,
    which is a fact about a moment rather than about this code: the first person
    to prepare a release made it false, and the failure pointed at the CHANGELOG
    instead of at the test. What actually matters is that nothing in this file
    writes to the real tree, whatever version the tree happens to say.

    """
    def snapshot():
        contents = {}
        for name in VERSIONED:
            with io.open(str(source_root.joinpath(name)),
                         encoding='utf-8') as handle:
                contents[name] = handle.read()
        return contents

    before = snapshot()
    yield
    assert snapshot() == before, \
        'a test in this file wrote to the real tree'


@pytest.fixture
def release(source_root):
    """`release.py`, loaded without running it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        'release_script', str(source_root.joinpath('release.py')))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def a_tree(release, source_root, tmpdir, monkeypatch):
    """A copy of the three files that state the version, and `HERE` pointing at
    it."""
    for name in VERSIONED:
        shutil.copyfile(str(source_root.joinpath(name)),
                        str(tmpdir.join(name)))
    monkeypatch.setattr(release, 'HERE', str(tmpdir))

    class Tree(object):
        path = str(tmpdir)

        def __init__(self):
            self.before = {name: self.read(name) for name in VERSIONED}

        def read(self, name):
            with io.open(os.path.join(str(tmpdir), name),
                         encoding='utf-8') as handle:
                return handle.read()

        def untouched(self):
            return all(self.read(name) == text
                       for name, text in self.before.items())

    return Tree()


@pytest.fixture
def no_subprocesses(release, monkeypatch):
    """Everything that would shell out, recorded instead of run."""
    ran = []
    monkeypatch.setattr(release, 'run',
                        lambda *command, **kwargs: ran.append(command))
    monkeypatch.setattr(release, 'output', lambda *command: '')
    monkeypatch.setattr(release, 'check_working_tree', lambda: None)
    monkeypatch.setattr(release, 'check_tag_is_free', lambda version: None)
    monkeypatch.setattr(release, 'check_artifacts', lambda version: None)
    monkeypatch.setattr(release, 'smoke_test', lambda version: None)
    monkeypatch.setattr(shutil, 'rmtree',
                        lambda path, **kwargs: None)
    return ran


class TestTheBootstrapRecipe(object):
    def test_it_names_the_version_that_was_asked_for(self, release):
        assert './release.py 4.0.1' in release.bootstrap('4.0.1')

    def test_it_is_four_lines_and_installs_nothing_itself(self, release):
        lines = release.bootstrap('4.0.1').strip().splitlines()
        assert len(lines) == 4
        assert lines[0].strip() == 'python3 -m venv .release-venv'
        assert lines[1].strip().endswith('-m pip install -U pip')
        assert lines[2].strip().endswith(
            '-m pip install -r requirements.txt -e .')

    def test_it_uses_this_platform_s_virtualenv_layout(self, release):
        wanted = 'Scripts' if os.name == 'nt' else 'bin'
        assert os.path.join('.release-venv', wanted, 'python') in \
            release.bootstrap()

    def test_git_ignores_the_environment_it_asks_for(self, source_root):
        with io.open(str(source_root.joinpath('.gitignore')),
                     encoding='utf-8') as handle:
            assert '.release-venv/' in handle.read()

    def test_flake8_does_not_lint_the_environment_it_asks_for(
            self, source_root):
        """Following the advice must not break the gate the advice is for."""
        with io.open(str(source_root.joinpath('tox.ini')),
                     encoding='utf-8') as handle:
            excluded = [line for line in handle.read().splitlines()
                        if line.startswith('exclude =')]
        assert excluded, 'tox.ini no longer tells flake8 what to skip'
        assert '.release-venv' in excluded[0]

    def test_contributing_documents_exactly_this_recipe(self, release,
                                                        source_root):
        with io.open(str(source_root.joinpath('CONTRIBUTING.md')),
                     encoding='utf-8') as handle:
            contributing = handle.read()
        for line in release.bootstrap('4.0.1').strip().splitlines():
            assert line.strip() in contributing, line.strip()
        # And that a second release can reuse it.
        assert '.release-venv/bin/python -m pip install -r requirements.txt' \
            ' -e .' in contributing


class TestAnInterpreterThatCannot(object):
    def test_an_old_python_says_so_and_writes_nothing(self, release, a_tree,
                                                      monkeypatch):
        monkeypatch.setattr(release.sys, 'version_info', (3, 8, 10))
        with pytest.raises(SystemExit) as raised:
            release.check_python('4.0.1')
        said = str(raised.value)
        assert '3.9 or newer' in said
        assert '3.8.10' in said
        assert 'python3 -m venv .release-venv' in said
        assert a_tree.untouched()

    def test_a_missing_gate_is_named_with_what_it_is_for(
            self, release, a_tree, monkeypatch):
        """The case that started this: no pytest in the interpreter used."""
        import importlib.util

        real = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util, 'find_spec',
            lambda name, *rest: None if name == 'pytest' else real(name, *rest))

        with pytest.raises(SystemExit) as raised:
            release.check_dependencies('4.0.1')
        said = str(raised.value)
        assert 'pytest' in said
        assert 'the test suite' in said
        assert './release.py 4.0.1' in said
        assert a_tree.untouched()

    @pytest.mark.parametrize('name', ['flake8', 'build', 'twine'])
    def test_each_of_the_release_tools_is_checked_for(self, release, name,
                                                      monkeypatch):
        import importlib.util

        real = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util, 'find_spec',
            lambda asked, *rest: None if asked == name else real(asked, *rest))
        with pytest.raises(SystemExit) as raised:
            release.check_dependencies('4.0.1')
        assert name in str(raised.value)

    @pytest.mark.parametrize('name', ['psutil', 'pyte', 'thebleep'])
    def test_the_runtime_dependencies_the_suite_needs_are_checked_for(
            self, release, name, monkeypatch):
        """Without these the suite fails on import, which is a worse way to
        find out."""
        import importlib.util

        real = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util, 'find_spec',
            lambda asked, *rest: None if asked == name else real(asked, *rest))
        with pytest.raises(SystemExit) as raised:
            release.check_dependencies('4.0.1')
        assert name in str(raised.value)

    def test_this_interpreter_passes(self, release):
        """The suite is running, so everything it needs is here."""
        release.check_python('4.0.1')
        release.check_dependencies('4.0.1')


class TestNothingIsWrittenBeforeTheGatesPass(object):
    def test_a_failed_prerequisite_check_leaves_the_tree_alone(
            self, release, a_tree, no_subprocesses, monkeypatch):
        monkeypatch.setattr(release, 'check_dependencies',
                            lambda version='': sys.exit('release.py: nope'))
        with pytest.raises(SystemExit):
            release.main(['release.py', '4.0.1'])
        assert a_tree.untouched()
        assert no_subprocesses == [], 'a gate ran after the check had failed'

    def test_a_failing_gate_leaves_the_tree_alone(
            self, release, a_tree, no_subprocesses, monkeypatch):
        """flake8 or the suite saying no must not cost a `git checkout`."""
        import subprocess

        def refuse(*command, **kwargs):
            raise subprocess.CalledProcessError(1, command)

        monkeypatch.setattr(release, 'run', refuse)
        with pytest.raises(subprocess.CalledProcessError):
            release.main(['release.py', '4.0.1'])
        assert a_tree.untouched()

    def test_the_gates_run_before_the_version_is_written(
            self, release, a_tree, no_subprocesses, monkeypatch):
        order = []
        monkeypatch.setattr(release, 'run', lambda *command, **kwargs:
                            order.append(command[2]))
        real = release.set_version
        monkeypatch.setattr(release, 'set_version',
                            lambda *arguments: (order.append('set_version'),
                                                real(*arguments))[1])
        release.main(['release.py', '4.0.1'])
        assert order.index('flake8') < order.index('set_version')
        assert order.index('pytest') < order.index('set_version')

    def test_a_failure_after_writing_puts_the_files_back(
            self, release, a_tree, no_subprocesses, monkeypatch):
        """The build, the artifact check or the smoke test going wrong."""
        monkeypatch.setattr(release, 'check_artifacts',
                            lambda version: sys.exit('release.py: no wheel'))
        with pytest.raises(SystemExit):
            release.main(['release.py', '4.0.1'])
        assert a_tree.untouched(), \
            'the tree was left saying it is a version that was never released'


class TestWhatItWritesWhenTheGatesPass(object):
    def test_the_version_and_today_reach_the_changelog(
            self, release, a_tree, no_subprocesses):
        import datetime

        release.main(['release.py', '4.0.1'])
        heading = '## 4.0.1 — {}'.format(
            datetime.date.today().isoformat())
        assert heading in a_tree.read('CHANGELOG.md')
        assert 'unreleased' not in a_tree.read('CHANGELOG.md').splitlines()[2]

    def test_the_version_reaches_setup_py_and_the_badge(self, release, a_tree,
                                                        no_subprocesses):
        release.main(['release.py', '4.0.1'])
        assert "VERSION = '4.0.1'" in a_tree.read('setup.py')
        assert 'badge/version-4.0.1-' in a_tree.read('README.md')
