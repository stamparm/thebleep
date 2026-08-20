# -*- coding: utf-8 -*-

from importlib.metadata import PackageNotFoundError, version
import pickle
import pytest
import os
import sys
import warnings
from unittest.mock import Mock, call, patch
from thebleep import cachefile
from thebleep.utils import default_settings, \
    memoize, get_closest, get_all_executables, replace_argument, \
    get_all_matched_commands, is_app, for_app, cache, \
    get_valid_history_without_current, get_close_matches, which
from thebleep.types import Command


@pytest.mark.parametrize('override, old, new', [
    ({'key': 'val'}, {}, {'key': 'val'}),
    ({'key': 'new-val'}, {'key': 'val'}, {'key': 'val'}),
    ({'key': 'new-val', 'unset': 'unset'}, {'key': 'val'}, {'key': 'val', 'unset': 'unset'})])
def test_default_settings(settings, override, old, new):
    settings.clear()
    settings.update(old)
    default_settings(override)(lambda _: _)(None)
    assert settings == new


def test_memoize():
    fn = Mock(__name__='fn')
    memoized = memoize(fn)
    memoized()
    memoized()
    fn.assert_called_once_with()


@pytest.mark.usefixtures('no_memoize')
def test_no_memoize():
    fn = Mock(__name__='fn')
    memoized = memoize(fn)
    memoized()
    memoized()
    assert fn.call_count == 2


class TestGetClosest(object):
    def test_when_can_match(self):
        assert 'branch' == get_closest('brnch', ['branch', 'status'])

    def test_when_cant_match(self):
        assert 'status' == get_closest('st', ['status', 'reset'])

    def test_without_fallback(self):
        assert get_closest('st', ['status', 'reset'],
                           fallback_to_first=False) is None


class TestWhich(object):
    """`which` replaced `shutil.which`, so it has to answer the same thing.

    Importing `shutil` cost three compression libraries before any rule could
    ask whether a program was installed, and several ask while they are being
    imported. The replacement is only worth having if it agrees, so this asks
    both of them about the same names -- ones that are there, ones that are
    not, ones given as a path, and the empty string.

    """

    @pytest.fixture(autouse=True)
    def not_memoized(self, monkeypatch):
        # `which` is memoized, and a memo built in another test would answer
        # instead of the code under test.
        monkeypatch.setattr(memoize, 'disabled', True)

    @pytest.mark.parametrize('program', [
        'python', 'python3', 'sh', 'ls', 'sort',
        'definitely-not-a-real-program-9d3f', '',
        'thebleep/utils.py', './setup.py', '/bin/sh', '/bin', '/'])
    def test_it_agrees_with_shutil(self, program):
        import shutil

        assert which(program) == shutil.which(program)

    def test_a_directory_is_not_a_program(self, tmpdir):
        directory = tmpdir.mkdir('bin')
        assert which(str(directory)) is None

    def test_a_file_on_the_path_is_found(self, tmpdir, monkeypatch):
        """And on Windows, found by the name you would actually type.

        `PATHEXT` is the list of extensions the shell lets you leave off, so a
        `.bat` there is what a file with the executable bit is on POSIX: the
        thing that runs when you type its stem.

        """
        name = 'made-up-tool.bat' if os.name == 'nt' else 'made-up-tool'
        binary = tmpdir.join(name)
        binary.write('#!/bin/sh\n')
        os.chmod(str(binary), 0o755)
        monkeypatch.setenv('PATH', str(tmpdir))
        # `normcase`, because the extension comes back spelled the way PATHEXT
        # spells it -- `.BAT` -- and the file on disk is `.bat`. On Windows
        # those are one file, and `shutil.which` answers the same way.
        assert os.path.normcase(which('made-up-tool')) \
            == os.path.normcase(str(binary))

    def test_a_file_that_cannot_be_run_is_not_found(self, tmpdir, monkeypatch):
        tmpdir.join('unrunnable').write('not executable\n')
        monkeypatch.setenv('PATH', str(tmpdir))
        assert which('unrunnable') is None


class TestGetCloseMatches(object):
    @patch('thebleep.utils.difflib_get_close_matches')
    def test_call_with_n(self, difflib_mock):
        get_close_matches('', [], 1)
        assert difflib_mock.call_args[0][2] == 1

    @patch('thebleep.utils.difflib_get_close_matches')
    def test_call_without_n(self, difflib_mock, settings):
        get_close_matches('', [])
        assert difflib_mock.call_args[0][2] == settings.get('num_close_matches')


def test_memoize_does_not_copy_the_output(mocker):
    """A memoized call must not cost anything proportional to the output.

    Pickling the command to build a cache key copied the whole output of the
    failed command, once per memoized call made about it.

    """
    dumps = mocker.patch('pickle.dumps', wraps=pickle.dumps)
    calls = []

    @memoize
    def counted(command):
        calls.append(command)
        return len(calls)

    command = Command('git brnch', 'x' * 100000)
    assert counted(command) == 1
    assert counted(command) == 1
    assert not dumps.called


# Kept before anything patches them, so that the tests which are *about* the
# disk cache can put the real thing back.
REAL_CACHEFILE = (cachefile.load, cachefile.save)


@pytest.fixture(autouse=True)
def no_disk_cache(mocker):
    """Keeps the tests off whatever the machine cached for itself."""
    mocker.patch('thebleep.cachefile.load', return_value=None)
    mocker.patch('thebleep.cachefile.save',
                 side_effect=lambda name, fingerprint, value: value)


@pytest.fixture
def get_aliases(mocker):
    mocker.patch('thebleep.shells.shell.get_aliases',
                 return_value=['vim', 'apt-get', 'fsck', 'bleep'])


@pytest.mark.usefixtures('no_memoize', 'get_aliases')
def test_get_all_executables():
    all_callables = get_all_executables()
    assert 'vim' in all_callables
    assert 'fsck' in all_callables
    assert 'bleep' not in all_callables


@pytest.fixture
def os_environ_pathsep(monkeypatch, path, pathsep):
    env = {'PATH': path}
    monkeypatch.setattr('os.environ', env)
    monkeypatch.setattr('os.pathsep', pathsep)
    return env


@pytest.mark.usefixtures('no_memoize', 'os_environ_pathsep')
@pytest.mark.parametrize('path, pathsep', [
    ('/foo:/bar:/baz:/foo/bar', ':'),
    (r'C:\\foo;C:\\bar;C:\\baz;C:\\foo\\bar', ';')])
def test_get_all_executables_pathsep(path, pathsep, no_disk_cache):
    with patch('os.scandir', return_value=[]) as scandir_mock:
        get_all_executables()
        scandir_mock.assert_has_calls([call(p) for p in path.split(pathsep)],
                                      True)


@pytest.mark.usefixtures('no_memoize', 'os_environ_pathsep')
@pytest.mark.parametrize('path, pathsep, excluded', [
    ('/foo:/bar:/baz:/foo/bar:/mnt/foo', ':', '/mnt/foo'),
    (r'C:\\foo;C:\\bar;C:\\baz;C:\\foo\\bar;Z:\\foo', ';', r'Z:\\foo')])
def test_get_all_executables_exclude_paths(path, pathsep, excluded, settings,
                                           no_disk_cache):
    settings.init()
    settings.excluded_search_path_prefixes = [excluded]
    with patch('os.scandir', return_value=[]) as scandir_mock:
        get_all_executables()
        path_list = path.split(pathsep)
        assert call(path_list[-1]) not in scandir_mock.mock_calls
        assert all(call(p) in scandir_mock.mock_calls for p in path_list[:-1])


@pytest.mark.parametrize('args, result', [
    (('apt-get instol vim', 'instol', 'install'), 'apt-get install vim'),
    (('git brnch', 'brnch', 'branch'), 'git branch')])
def test_replace_argument(args, result):
    assert replace_argument(*args) == result


@pytest.mark.parametrize('stderr, result', [
    (("git: 'cone' is not a git command. See 'git --help'.\n"
      '\n'
      'Did you mean one of these?\n'
      '\tclone'), ['clone']),
    (("git: 're' is not a git command. See 'git --help'.\n"
      '\n'
      'Did you mean one of these?\n'
      '\trebase\n'
      '\treset\n'
      '\tgrep\n'
      '\trm'), ['rebase', 'reset', 'grep', 'rm']),
    (('tsuru: "target" is not a tsuru command. See "tsuru help".\n'
      '\n'
      'Did you mean one of these?\n'
      '\tservice-add\n'
      '\tservice-bind\n'
      '\tservice-doc\n'
      '\tservice-info\n'
      '\tservice-list\n'
      '\tservice-remove\n'
      '\tservice-status\n'
      '\tservice-unbind'), ['service-add', 'service-bind', 'service-doc',
                            'service-info', 'service-list', 'service-remove',
                            'service-status', 'service-unbind'])])
def test_get_all_matched_commands(stderr, result):
    assert list(get_all_matched_commands(stderr)) == result


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, names, result', [
    ('/usr/bin/git diff', ['git', 'hub'], True),
    ('/bin/hdfs dfs -rm foo', ['hdfs'], True),
    ('git diff', ['git', 'hub'], True),
    ('hub diff', ['git', 'hub'], True),
    ('hg diff', ['git', 'hub'], False),
    # A command can be preceded by variables set just for it.
    ('TERM=xterm-256color ssh example.com', ['ssh'], True),
    ('GIT_TRACE=1 LANG=C git diff', ['git', 'hub'], True),
    ('GIT_TRACE=1 /usr/bin/git diff', ['git'], True),
    ('TERM=xterm-256color ssh example.com', ['term'], False),
    # ...but a plain assignment is not a call to anything.
    ('TERM=xterm-256color', ['ssh'], False),
    ('not-an=assignment diff', ['diff'], False)])
def test_is_app(script, names, result):
    assert is_app(Command(script, ''), *names) == result


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, at_least, result', [
    ('TERM=1 git', 1, False),
    ('TERM=1 git diff', 1, True),
    ('TERM=1 A=2 git', 1, False),
    ('TERM=1 A=2 git diff', 1, True)])
def test_is_app_at_least_counts_from_the_command(script, at_least, result):
    """`at_least` is about the command's own arguments, not the assignments."""
    assert is_app(Command(script, ''), 'git', at_least=at_least) == result


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, names, result', [
    ('/usr/bin/git diff', ['git', 'hub'], True),
    ('/bin/hdfs dfs -rm foo', ['hdfs'], True),
    ('git diff', ['git', 'hub'], True),
    ('hub diff', ['git', 'hub'], True),
    ('hg diff', ['git', 'hub'], False)])
def test_for_app(script, names, result):
    @for_app(*names)
    def match(command):
        return True

    assert match(Command(script, '')) == result


class TestCache(object):
    """`@cache` stores an answer until one of the files it named changes.

    It used to be `shelve`, which brought `dbm` and `pickle` with it, spread one
    logical database over however many files the available dbm backend felt like,
    needed an `atexit` handler to close it and a "removing possibly out-dated
    cache" path for moving between Python versions. It is `cachefile` now, which
    is what the rule pack and the PATH listing already used.

    """

    @pytest.fixture(autouse=True)
    def cache_home(self, tmpdir, os_environ, no_cache, no_disk_cache,
                   monkeypatch):
        # Both of those are requested so that they are set up first and this
        # undoes them. The suite as a whole keeps every test off the disk cache;
        # these tests are the ones about it.
        monkeypatch.setattr('thebleep.utils.cache.disabled', False)
        monkeypatch.setattr('thebleep.cachefile.load', REAL_CACHEFILE[0])
        monkeypatch.setattr('thebleep.cachefile.save', REAL_CACHEFILE[1])
        os_environ['XDG_CACHE_HOME'] = str(tmpdir.mkdir('cache'))
        return tmpdir

    @pytest.fixture
    def dependency(self, cache_home):
        watched = cache_home.join('watched')
        watched.write('first')
        return watched

    @pytest.fixture
    def counted(self, dependency):
        """A cached function that says how many times it really ran."""
        calls = []

        @cache(str(dependency))
        def fn():
            calls.append(1)
            return 'answer-{}'.format(len(calls))

        fn.calls = calls
        return fn

    def test_the_first_call_computes_and_the_second_does_not(self, counted):
        assert counted() == 'answer-1'
        assert counted() == 'answer-1'
        assert len(counted.calls) == 1

    def test_a_changed_dependency_expires_it(self, counted, dependency,
                                             no_memoize):
        assert counted() == 'answer-1'
        os.utime(str(dependency), (0, 0))
        assert counted() == 'answer-2'

    def test_a_dependency_that_is_not_there_is_not_an_error(self, cache_home,
                                                            no_memoize):
        @cache(str(cache_home.join('never-existed')))
        def fn():
            return 'answer'

        assert fn() == 'answer'
        assert fn() == 'answer'

    def test_an_unwritable_cache_still_answers(self, cache_home, os_environ,
                                               no_memoize, dependency):
        blocked = cache_home.join('not-a-directory')
        blocked.write('')
        os_environ['XDG_CACHE_HOME'] = str(blocked)

        @cache(str(dependency))
        def fn():
            return 'answer'

        assert fn() == 'answer'

    def test_two_functions_whose_names_share_a_prefix(self, dependency,
                                                      no_memoize):
        """The identity used to be `repr(fn).split('at')[0]`.

        That is the repr up to the first literal "at", so `_get_operations`
        became `<function _get_oper` -- and any two functions in a module whose
        names agree up to their first "at" shared one entry and each got the
        other's answer.

        """
        @cache(str(dependency))
        def _get_operations():
            return 'operations'

        @cache(str(dependency))
        def _get_operators():
            return 'operators'

        assert _get_operations() == 'operations'
        assert _get_operators() == 'operators'
        assert _get_operations() == 'operations'

    def test_different_arguments_are_remembered_separately(self, dependency,
                                                           no_memoize):
        """`omnienv_no_such_command` caches per app name."""
        @cache(str(dependency))
        def commands_for(app):
            return ['{}-commands'.format(app)]

        assert commands_for('pyenv') == ['pyenv-commands']
        assert commands_for('rbenv') == ['rbenv-commands']
        assert commands_for('pyenv') == ['pyenv-commands']

    def test_disabling_it_calls_through_every_time(self, counted, monkeypatch,
                                                   no_memoize):
        monkeypatch.setattr('thebleep.utils.cache.disabled', True)
        assert counted() == 'answer-1'
        assert counted() == 'answer-2'

    def test_it_leaves_no_database_behind(self, counted, cache_home):
        from thebleep import cachefile

        counted()
        assert not list(cachefile.directory().glob('rules.db*'))
        assert list(cachefile.directory().glob('*.cache'))

    def test_clearing_the_cache_removes_it(self, counted, no_memoize):
        from thebleep import cachefile

        assert counted() == 'answer-1'
        assert cachefile.clear() >= 1
        assert counted() == 'answer-2'


@pytest.mark.usefixtures('no_memoize')
class TestGetValidHistoryWithoutCurrent(object):
    @pytest.fixture(autouse=True)
    def fail_on_warning(self):
        warnings.simplefilter('error')
        yield
        warnings.resetwarnings()

    @pytest.fixture(autouse=True)
    def history(self, mocker):
        mock = mocker.patch('thebleep.shells.shell.get_history')
        #  Passing as an argument causes `UnicodeDecodeError`
        #  with newer pytest and python 2.7
        mock.return_value = ['le cat', 'bleep', 'ls cat',
                             'diff x', 'nocommand x', u'café ô']
        return mock

    @pytest.fixture(autouse=True)
    def alias(self, mocker):
        return mocker.patch('thebleep.utils.get_alias',
                            return_value='bleep')

    @pytest.fixture(autouse=True)
    def bins(self, tmpdir, os_environ):
        # Real files with the executable bit on, rather than mocked directory
        # entries: what counts as a command is now a question about the file,
        # and a mock cannot answer it.
        directory = tmpdir.mkdir('bin')
        for name in ['diff', 'ls', u'café']:
            entry = directory.join(name)
            entry.write('#!/bin/sh\nexit 0\n')
            os.chmod(str(entry), 0o755)
        os_environ['PATH'] = str(directory)
        os_environ['XDG_CACHE_HOME'] = str(tmpdir.mkdir('cache'))
        return directory

    @pytest.mark.parametrize('script, result', [
        ('le cat', ['ls cat', 'diff x', u'café ô']),
        ('diff x', ['ls cat', u'café ô']),
        ('bleep', ['ls cat', 'diff x', u'café ô']),
        (u'cafe ô', ['ls cat', 'diff x', u'café ô']),
    ])
    def test_get_valid_history_without_current(self, script, result):
        command = Command(script, '')
        assert get_valid_history_without_current(command) == result


class TestInstallationVersion(object):
    def test_the_installed_version_is_reported(self):
        from thebleep.utils import get_installation_version

        assert get_installation_version() == version('thebleep')

    def test_a_checkout_that_was_never_installed(self, mocker):
        """`--version` should say so rather than raising."""
        from thebleep import utils

        mocker.patch('importlib.metadata.version',
                     side_effect=PackageNotFoundError('thebleep'))
        assert utils.get_installation_version() == 'unknown'


@pytest.mark.usefixtures("no_memoize")
class TestAnEmptyPathEntry(object):
    """`PATH=:/usr/bin` -- an empty entry means the current directory.

    `shutil.which` honours that and this did not, which was not a cosmetic
    disagreement: `replay.is_inert` reads "not on `PATH`" as "there is nothing
    there to run, so running it again is free", so a local `./deploy` that the
    shell had just found and run was run a second time without being asked
    about.

    """

    @pytest.fixture
    def a_program_here(self, tmpdir, monkeypatch):
        program = tmpdir.join('localcmd')
        program.write('#!/bin/sh\n')
        os.chmod(str(program), 0o755)
        monkeypatch.chdir(str(tmpdir))
        return 'localcmd'

    @pytest.mark.parametrize('path', [':/usr/bin', '/usr/bin:',
                                      '/usr/bin::/bin', ':', ''])
    def test_it_agrees_with_shutil(self, a_program_here, path, monkeypatch):
        import shutil

        monkeypatch.setenv('PATH', path)
        assert which(a_program_here) == shutil.which(a_program_here)

    @pytest.mark.skipif(sys.platform == 'win32',
                        reason='an extensionless file is not runnable on'
                               ' Windows, so `shutil.which` says no too --'
                               ' which the parity test above already covers')
    def test_the_command_is_not_treated_as_absent(self, a_program_here,
                                                  monkeypatch):
        monkeypatch.setenv('PATH', ':/usr/bin')
        assert which(a_program_here) is not None
