# -*- coding: utf-8 -*-

"""A machine with no home directory to expand `~` against.

`Path.expanduser()` raises `RuntimeError: Could not determine home directory.`
when it cannot work one out. On POSIX the password database answers even with
`HOME` unset, so it effectively never fires; on Windows there is no such
fallback, so no `USERPROFILE` and no `HOME` means the exception -- a service
account, a stripped container, or a test that cleared the environment.

Ten call sites asked pathlib that question and every one of them took the run
down with it, including `cachefile` and `rulepack`, which are on the path of
every correction. It was hidden until then by a monkeypatch of
`pathlib.Path.expanduser`, and removing that patch without answering the question
here is what exposed it.

The condition is reproduced rather than mocked away: `os.path.expanduser` is made
to behave the way it does on Windows with nowhere to expand to -- handing the `~`
straight back -- which is exactly what makes pathlib raise. That runs the same on
every platform, so this is not a test only Windows can fail.

"""

import os
import os.path
import tempfile
import pytest
from thebleep.types import Command


@pytest.fixture
def nowhere_to_call_home(monkeypatch, tmpdir):
    """No home directory, and a working directory we can inspect afterwards."""
    monkeypatch.setattr('os.path.expanduser', lambda path: path)
    monkeypatch.chdir(tmpdir)
    for variable in ('HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH',
                     'XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
        os.environ.pop(variable, None)
    return tmpdir


def test_it_is_really_the_condition_that_broke_windows(nowhere_to_call_home):
    """Guards the guard: without the condition, the rest of this proves nothing.

    Python 3.11 and later ask `os.path.expanduser` and raise when it hands the
    `~` back, so patching it reproduces the Windows failure exactly. Before that,
    pathlib asked the platform for the home directory itself -- reachable only by
    actually being on Windows with no USERPROFILE -- so the raise is asserted
    where it can be reached and the setup is asserted everywhere.

    """
    from pathlib import Path

    assert os.path.expanduser('~') == '~', 'the fixture did not take'

    try:
        Path('~', '.thebleep').expanduser()
    except RuntimeError as error:
        assert 'home directory' in str(error)
        return
    pytest.skip("this interpreter's pathlib does not consult "
                "os.path.expanduser, so the raise cannot be reached from here")


def test_settings_still_load(nowhere_to_call_home):
    from thebleep import conf

    conf.settings.init()
    assert conf.settings.user_dir
    assert conf.settings.rules


def test_the_caches_still_have_somewhere_to_go(nowhere_to_call_home):
    from thebleep import cachefile, rulepack

    assert cachefile.directory()
    assert rulepack._cache_path()
    # One place decides where caches live, so the pack lives under it.
    assert rulepack._cache_path().parent == cachefile.directory()


@pytest.mark.parametrize('what', ['config', 'cache'])
def test_nothing_is_written_to_a_directory_called_tilde(nowhere_to_call_home,
                                                        what):
    """`~/.config/thebleep` with no home is a directory named `~` in the
    working directory, which is where the user happened to be standing."""
    from thebleep import cachefile, conf

    conf.settings.init()
    cachefile.save('probe', (), 'value')

    where = conf.settings.user_dir if what == 'config' else cachefile.directory()
    # By component, not by substring: a Windows short path is full of tildes,
    # `C:\Users\RUNNER~1\AppData\Local\Temp` among them, and none of them is the
    # unexpanded `~` this is looking for.
    assert '~' not in where.parts, where
    assert where.is_absolute(), where
    assert str(where).startswith(tempfile.gettempdir()), where
    assert not nowhere_to_call_home.join('~').check(), \
        'a directory named "~" was created in the working directory'


def test_a_correction_still_happens(nowhere_to_call_home):
    """The whole point: the tool works, it does not merely start."""
    from thebleep import conf
    from thebleep.corrector import get_corrected_commands

    conf.settings.init()
    command = Command(u'git brnch',
                      u"git: 'brnch' is not a git command. See 'git --help'.\n"
                      u"\nThe most similar command is\n\tbranch\n")
    corrections = [correction.script
                   for correction in get_corrected_commands(command)]
    assert corrections[0] == 'git branch', corrections


@pytest.mark.parametrize('path, expanded', [
    ('~/x', False),
    ('~', False),
    ('/tmp/x', True),
    ('relative/x', True),
])
def test_expanduser_never_raises(nowhere_to_call_home, path, expanded):
    from thebleep.system import expanduser

    result = expanduser(path)
    assert (not str(result).startswith('~')) is expanded


def test_a_path_that_cannot_be_expanded_simply_does_not_exist(
        nowhere_to_call_home):
    """Which is the right answer for every caller that only reads.

    `workon_doesnt_exists`, `path_from_history`, the shells' "can I edit your
    startup file" check: each of them expands a `~` path and immediately asks
    whether it is there.

    """
    from thebleep.system import expanduser

    assert not expanduser('~/.virtualenvs').exists()
    assert not expanduser('~/.bashrc').exists()


def test_home_is_found_when_there_is_one(monkeypatch, tmpdir):
    """The ordinary case, so the fallback cannot quietly become the only path."""
    from thebleep import cachefile, conf
    from thebleep.system import expanduser

    home = tmpdir.mkdir('home')
    # A leading `~` and nothing else, which is all the real one expands. A
    # `replace('~', home, 1)` also rewrites the tilde in a Windows short name
    # like `C:\Users\RUNNER~1`, and then this passes while measuring nonsense.
    monkeypatch.setattr(
        'os.path.expanduser',
        lambda path: str(home) + path[1:] if path.startswith('~') else path)
    for variable in ('XDG_CONFIG_HOME', 'XDG_CACHE_HOME'):
        os.environ.pop(variable, None)

    assert expanduser('~/x') == expanduser(str(home.join('x')))
    conf.settings.init()
    assert str(conf.settings.user_dir).startswith(str(home))
    assert str(cachefile.directory()).startswith(str(home))


class TestTheFallbackDirectory(object):
    """`/tmp/thebleep-cache-<user>` is a name anybody can work out.

    What goes in it is `rulepack`'s pack file, which the next correction
    `marshal.loads`es and `exec`s. So a local attacker who created that
    directory first, with a pack of their own in it, ran their code as this
    user -- and the directory was created with whatever the umask allowed.

    """

    @pytest.fixture
    def elsewhere(self, monkeypatch, tmpdir):
        """A temporary directory of our own to be the shared `/tmp`."""
        shared = tmpdir.mkdir('shared')
        monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(shared))
        from thebleep.system import paths

        monkeypatch.setattr(paths, '_UNPREDICTABLE', {})
        return shared

    @pytest.mark.skipif(not hasattr(os, 'geteuid'),
                        reason='Windows has no POSIX mode to check')
    def test_it_is_created_private(self, nowhere_to_call_home, elsewhere):
        import stat
        from thebleep.system import paths

        where = paths.writable('~/.cache/thebleep', 'cache')
        assert stat.S_IMODE(os.stat(str(where)).st_mode) == 0o700

    @pytest.mark.skipif(not hasattr(os, 'geteuid'),
                        reason='Windows has no POSIX mode to check')
    def test_one_left_group_writable_by_an_older_release_is_tightened(
            self, nowhere_to_call_home, elsewhere):
        """Refusing it outright would mean a rebuilt rule pack on every
        correction forever; the owner is the part that cannot be repaired."""
        import getpass
        import stat
        from thebleep.system import paths

        existing = elsewhere.mkdir('thebleep-cache-{}'.format(
            getpass.getuser()))
        os.chmod(str(existing), 0o775)

        where = paths.writable('~/.cache/thebleep', 'cache')
        assert str(where) == str(existing)
        assert stat.S_IMODE(os.stat(str(where)).st_mode) == 0o700

    def test_somebody_elses_directory_is_not_used(self, nowhere_to_call_home,
                                                  elsewhere, monkeypatch):
        """The predictable name is refused, whatever it works out to be.

        Not `getpass.getuser()` to work it out: with the environment cleared,
        that falls through to the `pwd` module, which Windows does not have.
        `writable` wraps it in a try/except for exactly that reason, and a test
        calling it directly does not get that.

        """
        from thebleep.system import paths

        # Where it goes when the predictable name is free, which is the
        # predictable name itself.
        monkeypatch.setattr(paths, '_is_ours', lambda path: True)
        predictable = str(paths.writable('~/.cache/thebleep', 'cache'))

        # And where it goes when that name is somebody else's, which is the
        # case that cannot be repaired.
        monkeypatch.setattr(paths, '_is_ours', lambda path: False)
        refused = str(paths.writable('~/.cache/thebleep', 'cache'))

        assert refused != predictable
        assert refused.startswith(str(elsewhere))

    def test_and_everything_still_agrees_where_that_is(
            self, nowhere_to_call_home, elsewhere, monkeypatch):
        """The pack lives under the cache directory and has to be found
        again, so the unpredictable name is chosen once."""
        from thebleep.system import paths

        monkeypatch.setattr(paths, '_is_ours', lambda path: False)
        assert (str(paths.writable('~/.cache/thebleep', 'cache'))
                == str(paths.writable('~/.cache/thebleep', 'cache')))
