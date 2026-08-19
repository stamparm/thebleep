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


def _is_absolute_enough(path):
    """Whether a path in the recipe resolves somewhere other than the checkout.

    Deliberately about the string and nothing else -- no `os.path`, no `HOME`.
    `os.path.isabs('/x')` is True on POSIX and False on Windows, and the suite
    clears the environment, so anything that consults either answers differently
    depending on where it runs. What has to be true is that a shell would not
    resolve this against the working directory: it begins with `~`, or with a
    separator, or with a drive letter.
    """
    return (path.startswith('~')
            or path.startswith(('/', '\\'))
            or (len(path) > 1 and path[1] == ':'))


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
        assert lines[0].strip() == ('python3 -m venv '
                                    + release.release_venv())
        assert lines[1].strip().endswith('-m pip install -U pip')
        assert lines[2].strip().endswith(
            '-m pip install -r requirements.txt -e .')

    @pytest.mark.parametrize('name', ['posix', 'nt'])
    def test_the_environment_is_not_in_the_checkout(self, release, monkeypatch,
                                                    name):
        """The whole reason it moved.

        A virtualenv in the working tree is somebody else's Python inside the
        project: git has to be told to ignore it, flake8 has to be told not to
        lint it, and `check_working_tree` then refuses to release past anything
        it was not told about. It used to be `.release-venv` in the root, and
        that is what it cost.

        The property is that the path is not a *relative* one, since a relative
        path is resolved against the checkout -- and that is a question about the
        string, answered without touching the filesystem or the environment. It
        used to `expanduser` the path and join it onto the source root, which
        said the wrong thing twice: `expanduser` cannot expand `~` in a suite
        that clears the environment, so the join put `~` inside the repository
        and the test failed on the one platform where nobody had run it.

        """
        monkeypatch.setattr(release.os, 'name', name)
        found = 0
        for line in release.bootstrap('4.0.1').strip().splitlines():
            for word in line.split():
                if 'release-venv' not in word:
                    continue
                found += 1
                assert _is_absolute_enough(word), word
        assert found >= 2, 'the recipe stopped naming the environment'

    @pytest.mark.parametrize('name, expected', [('posix', 'bin'),
                                                ('nt', 'Scripts')])
    def test_it_uses_the_running_platform_s_virtualenv_layout(
            self, release, monkeypatch, name, expected):
        """Both, on whichever one the suite happens to be running on."""
        monkeypatch.setattr(release.os, 'name', name)
        assert '/{}/python'.format(expected) in release.bootstrap()

    def test_the_lines_are_written_for_a_shell_not_for_os_path(self, release,
                                                               monkeypatch):
        """Forward slashes even on Windows: these get pasted into a shell."""
        monkeypatch.setattr(release.os, 'name', 'nt')
        assert '\\\\' not in release.bootstrap()

    @pytest.mark.parametrize('name, where', [('posix', '~/Temp/elsewhere'),
                                             ('nt', 'D:/Temp/elsewhere')])
    def test_the_location_can_be_said_outright(self, release, monkeypatch,
                                               name, where):
        """`THEBLEEP_RELEASE_VENV`, and the whole recipe follows it.

        The interpreter inside it is asked for rather than spelled `/bin/python`,
        which is only where POSIX keeps it -- and asserting that on a Windows
        runner, where `bootstrap` correctly says `Scripts`, is a test being wrong
        about the code rather than the other way round.

        """
        monkeypatch.setattr(release.os, 'name', name)
        monkeypatch.setenv('THEBLEEP_RELEASE_VENV', where)
        recipe = release.bootstrap('4.0.1')
        assert 'python3 -m venv {}'.format(where) in recipe
        assert '{} ./release.py 4.0.1'.format(
            release.venv_python()) in recipe
        assert release.venv_python().startswith(where + '/'), \
            'the interpreter is not inside the environment that was named'
        assert '.cache' not in recipe

    def test_a_leftover_from_the_old_location_is_still_ignored(
            self, source_root):
        """Anybody who made one the old way should not see it in `git status`
        or have flake8 walk into it."""
        with io.open(str(source_root.joinpath('.gitignore')),
                     encoding='utf-8') as handle:
            assert '.release-venv/' in handle.read()
        with io.open(str(source_root.joinpath('tox.ini')),
                     encoding='utf-8') as handle:
            excluded = [line for line in handle.read().splitlines()
                        if line.startswith('exclude =')]
        assert excluded, 'tox.ini no longer tells flake8 what to skip'
        assert '.release-venv' in excluded[0]

    def test_contributing_documents_exactly_this_recipe(self, release,
                                                        source_root):
        """Against the POSIX spelling, and asked for by name.

        A document has to pick one, and it picked that one -- so comparing it
        with whatever this platform renders made the check fail on Windows, where
        the recipe says `.release-venv\\Scripts\\python`. What is worth holding
        is that the words in CONTRIBUTING are the words the script prints, not
        that CONTRIBUTING was written on a particular kind of machine.

        """
        with io.open(str(source_root.joinpath('CONTRIBUTING.md')),
                     encoding='utf-8') as handle:
            contributing = handle.read()

        recipe = release.bootstrap('4.0.1',
                                   python=release.POSIX_VENV_PYTHON)
        for line in recipe.strip().splitlines():
            assert line.strip() in contributing, line.strip()
        # And that a second release can reuse it.
        assert '{} -m pip install -r requirements.txt -e .'.format(
            release.POSIX_VENV_PYTHON) in contributing


class TestAnInterpreterThatCannot(object):
    def test_an_old_python_says_so_and_writes_nothing(self, release, a_tree,
                                                      monkeypatch):
        monkeypatch.setattr(release.sys, 'version_info', (3, 8, 10))
        with pytest.raises(SystemExit) as raised:
            release.check_python('4.0.1')
        said = str(raised.value)
        assert '3.9 or newer' in said
        assert '3.8.10' in said
        assert 'python3 -m venv ' + release.release_venv() in said
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
