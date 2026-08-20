# -*- encoding: utf-8 -*-

"""What the alias is told to run.

The alias is shell code that calls The Bleep again, and for most of this
project's life it called it by the one name an installed copy has. A clone had
no way to say otherwise, so working on a checkout meant the shell going back to
whatever was installed -- 4.0.0 correcting commands while 4.0.3 was being
written, with nothing anywhere to say so.

The rule under test: the answer follows how this process was started, and
nothing else guesses.

"""

import os
import shutil
import sys
import pytest
from thebleep import invocation
from thebleep.shells import Bash, Zsh, Fish, Generic, Tcsh


@pytest.fixture
def started_as_the_package(monkeypatch):
    """As `python -m thebleep`, which is what a clone is run with."""
    monkeypatch.setattr(sys, 'argv', [invocation._main_path(), '--alias'])


@pytest.fixture(autouse=True)
def no_override(monkeypatch):
    monkeypatch.delenv(invocation.OVERRIDE_ENV, raising=False)


class TestTheOrdinaryAnswer(object):
    def test_an_installed_copy_is_called_by_name(self):
        """Which is how the suite itself sees it, and every alias test with
        it."""
        assert invocation.command() == 'thebleep'

    def test_another_module_run_with_dash_m_is_not_us(self, monkeypatch):
        """The regression this very file was written after.

        `python -m pytest` puts *pytest's* `__main__.py` in `sys.argv[0]`, and
        a check that only looked at the file name took it for ours -- so the
        test suite quietly rewrote every alias it was checking.

        """
        monkeypatch.setattr(
            sys, 'argv', [os.path.join('elsewhere', '__main__.py')])
        assert invocation.command() == 'thebleep'

    def test_no_argv_at_all_is_not_a_clone(self, monkeypatch):
        monkeypatch.setattr(sys, 'argv', [''])
        assert invocation.command() == 'thebleep'


@pytest.mark.usefixtures('started_as_the_package')
class TestRunFromAClone(object):
    def test_it_names_the_interpreter_and_the_file(self):
        """Asked of the words, not of the quoted line.

        A Windows path holds a colon and backslashes, so `shlex.quote` wraps it
        -- and this asserted on the end of the quoted string, which is a quote.
        The words are what the function is about; the quoting belongs to
        whichever shell is asking.

        """
        words = invocation.parts()
        assert words[0] == sys.executable
        assert words[1].endswith(os.path.join('thebleep', '__main__.py'))

    def test_the_file_it_names_can_be_run(self):
        """The point of naming a file rather than `-m thebleep`: no
        environment variable in front of it and no dependence on the working
        directory."""
        assert os.path.isfile(invocation._main_path())

    def test_an_installed_copy_is_still_called_by_name(self, monkeypatch):
        """`python -m thebleep` against a copy in `site-packages` is an
        ordinary way to reach an installed tool -- there is no clone to
        prefer."""
        monkeypatch.setattr(invocation, '_checkout_root', lambda: None)
        assert invocation.command() == 'thebleep'

    def test_a_path_with_a_space_in_it_is_quoted(self, monkeypatch):
        monkeypatch.setattr(sys, 'executable', '/opt/some python/bin/python3')
        assert "'/opt/some python/bin/python3'" in invocation.command()

    @pytest.mark.parametrize('shell', [Bash, Zsh, Generic, Fish])
    def test_the_alias_it_writes_runs_the_clone(self, shell, set_shell):
        """Not `thebleep`, which would be whatever is installed.

        Compared against the shell's own `_invocation`, because that is where
        the quoting is decided -- `invocation.command()` only ever speaks POSIX.
        Fish is in the list because its alias is built positionally and is
        therefore worth its own look.

        """
        set_shell(shell)
        written = shell()._invocation()
        assert written != invocation.ENTRY_POINT
        for text in (shell().app_alias('bleep'),
                     shell().app_alias_loader('bleep')):
            assert written in text
            assert 'thebleep --alias' not in text

    def test_tcsh_says_so_when_it_cannot_hold_the_path(self, set_shell):
        """A tcsh alias body is single-quoted and cannot contain a quote, so a
        path needing quotes cannot go in one at all.

        On Windows that is every path -- a drive colon and backslashes are
        enough for `shlex.quote` -- which is how this turned up: a test that
        asserted the clone was named passed on Linux and failed on Windows.

        """
        set_shell(Tcsh)
        written = Tcsh()._invocation()
        if "'" in invocation.command():
            assert written == invocation.ENTRY_POINT
        else:
            assert written in Tcsh().app_alias('bleep')


class TestTheOverride(object):
    def test_it_is_used_exactly_as_written(self, os_environ):
        os_environ[invocation.OVERRIDE_ENV] = 'my-wrapper --flag'
        assert invocation.command() == 'my-wrapper --flag'

    def test_it_beats_a_clone(self, os_environ, started_as_the_package):
        os_environ[invocation.OVERRIDE_ENV] = 'my-wrapper'
        assert invocation.command() == 'my-wrapper'

    def test_an_empty_one_is_not_an_answer(self, os_environ):
        os_environ[invocation.OVERRIDE_ENV] = ''
        assert invocation.command() == 'thebleep'


class TestTheCheckout(object):
    def test_the_repository_is_one(self, source_root):
        assert invocation._checkout_root() == str(source_root)

    def test_a_package_without_a_setup_py_beside_it_is_not(self, monkeypatch,
                                                           tmpdir):
        package = tmpdir.mkdir('site-packages').mkdir('thebleep')
        monkeypatch.setattr(invocation, '__file__',
                            str(package.join('invocation.py')))
        assert invocation._checkout_root() is None


class TestACheckoutAtAPathWithASpace(object):
    """`~/My Projects/thebleep` -- which used to produce a broken alias.

    `Generic.app_alias` wraps its body in single quotes, and the quoting
    `self.quote` puts around a path with a space in it puts quotes *inside* that
    body. Interpolated as it stood, the first of those closed the alias early
    and the rest failed with a message naming neither the path nor the reason.

    """

    @pytest.fixture
    def spaced(self, monkeypatch):
        monkeypatch.setattr(
            invocation, 'parts',
            lambda: ['/opt/some python/bin/python3',
                     '/opt/My Projects/thebleep/__main__.py'])

    def test_the_alias_still_parses(self, spaced, set_shell, tmpdir):
        """In a real shell, because that is the only thing that settles it."""
        import subprocess

        set_shell(Generic)
        alias = Generic().app_alias('bleep')
        script = tmpdir.join('alias.sh')
        script.write(alias + '\nalias bleep\n')

        for interpreter in ('bash', 'dash', 'sh'):
            if not shutil.which(interpreter):
                continue
            done = subprocess.run([interpreter, '-c',
                                   '. {}'.format(str(script))],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=10)
            assert done.returncode == 0, done.stdout
            # And the path survived, quotes and all.
            assert b'/opt/My Projects/thebleep/__main__.py' in done.stdout

    def test_tcsh_says_so_instead(self, spaced, set_shell):
        """tcsh has no way to spell an embedded quote, so it falls back."""
        set_shell(Tcsh)
        assert Tcsh()._invocation() == invocation.ENTRY_POINT
