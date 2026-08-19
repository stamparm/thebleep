# -*- coding: utf-8 -*-

import os
import pytest
from thebleep.shells import Nushell


@pytest.mark.usefixtures('no_memoize', 'no_cache')
class TestNushell(object):
    @pytest.fixture
    def shell(self):
        return Nushell()

    @pytest.fixture(autouse=True)
    def Popen(self, mocker):
        return mocker.patch('thebleep.shells.nushell.Popen')

    def test_the_correction_is_not_run_by_us(self, shell):
        """Nushell has no `eval`, so it is put in the line editor instead."""
        assert not shell.can_run_corrections()
        assert shell.can_edit_buffer()

    def test_app_alias(self, shell):
        alias = shell.app_alias('bleep')
        assert 'def bleep [...args] {' in alias
        assert 'def BLEEP [...args] {' in shell.app_alias('BLEEP')
        assert 'TB_SHELL: "nu"' in alias
        assert 'TB_ALIAS: "bleep"' in alias
        assert 'commandline edit --replace $fixed_command' in alias
        # Not `complete`: that would capture stderr, which is where the
        # suggestion and the question about it are written.
        assert 'complete' not in alias
        assert 'do --ignore-errors' in alias

    def test_app_alias_loader_is_the_alias(self, shell):
        """There is no `eval` to define it from a string on first use."""
        assert shell.app_alias_loader('bleep') == shell.app_alias('bleep')

    @pytest.mark.parametrize('commands, chained', [
        (['git push'], 'git push'),
        (['git pull', 'git push'], 'try { git pull; git push }'),
        (['a', 'b', 'c'], 'try { a; b; c }')])
    def test_and_(self, shell, commands, chained):
        assert shell.and_(*commands) == chained

    @pytest.mark.parametrize('commands, chained', [
        (['a'], 'a'),
        (['a', 'b'], 'try { a } catch { b }'),
        (['a', 'b', 'c'], 'try { a } catch { try { b } catch { c } }')])
    def test_or_(self, shell, commands, chained):
        assert shell.or_(*commands) == chained

    @pytest.mark.parametrize('given, quoted', [
        ('feature', 'feature'),
        ('path/to/x.py', 'path/to/x.py'),
        ('my branch', "'my branch'"),
        ('a;rm -rf ~', "'a;rm -rf ~'"),
        ('$(id)', "'$(id)'"),
        ('a|b', "'a|b'"),
        # A single-quoted Nushell string is literal all the way through, so a
        # value holding one has to be written the other way.
        ("it's", '"it\'s"'),
        ('a"b', '\'a"b\''),
        ('say "it\'s"', '"say \\"it\'s\\""'),
        ('back\\slash', "'back\\slash'"),
        # A bare `-x` would be read as a flag.
        ('-x', "'-x'"),
        ('~home', "'~home'"),
        ('', "''")])
    def test_quote(self, shell, given, quoted):
        assert shell.quote(given) == quoted

    def test_the_xdg_directory_comes_first(self, shell, os_environ, tmpdir):
        """On every platform, because that is the order Nushell reads them in.

        Asking the platform first sent this looking in `~/Library/Application
        Support` on a macOS machine whose Nushell was using the XDG directory.

        """
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        assert shell._config_dirs()[0] == os.path.join(str(tmpdir), 'nushell')

    @pytest.mark.parametrize('platform, name, expected', [
        ('linux', 'posix', os.path.join('~', '.config', 'nushell')),
        ('darwin', 'posix',
         os.path.join('~', 'Library', 'Application Support', 'nushell')),
    ])
    def test_the_platform_answers_when_xdg_says_nothing(
            self, shell, os_environ, monkeypatch, platform, name, expected):
        """Every branch is checked from here, not only the one we run on.

        The macOS branch was wrong and only the macOS runner said so, which is
        the slowest possible way to find out.

        """
        monkeypatch.setattr('sys.platform', platform)
        monkeypatch.setattr('os.name', name)
        home = os.path.expanduser('~')
        assert shell._config_dirs()[0] == os.path.join(
            home, *expected.split(os.sep)[1:])

    def test_windows_uses_appdata(self, shell, os_environ, monkeypatch):
        monkeypatch.setattr('sys.platform', 'win32')
        monkeypatch.setattr('os.name', 'nt')
        os_environ['APPDATA'] = os.path.join('C:', 'Users', 'x', 'AppData')
        assert shell._config_dirs()[0] == os.path.join(
            os_environ['APPDATA'], 'nushell')

    def test_windows_honours_xdg_too(self, shell, os_environ, monkeypatch,
                                     tmpdir):
        """It was in the branch Windows never took, so Windows never read it."""
        monkeypatch.setattr('sys.platform', 'win32')
        monkeypatch.setattr('os.name', 'nt')
        os_environ['APPDATA'] = os.path.join('C:', 'Users', 'x', 'AppData')
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        assert shell._config_dirs()[0] == os.path.join(str(tmpdir), 'nushell')

    def test_macos_also_looks_in_the_xdg_default(self, shell, os_environ,
                                                 monkeypatch):
        """Which of the two a given Nushell build uses is not a question this
        has to answer: it can look in both."""
        monkeypatch.setattr('sys.platform', 'darwin')
        monkeypatch.setattr('os.name', 'posix')
        places = shell._config_dirs()
        assert any(place.endswith(os.path.join('.config', 'nushell'))
                   for place in places)
        assert any('Application Support' in place for place in places)

    def test_no_history_yet_names_the_default_format(
            self, shell, os_environ, tmpdir):
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        assert shell._get_history_file_name() == os.path.join(
            str(tmpdir), 'nushell', 'history.txt')

    @pytest.mark.parametrize('name', ['history.txt', 'history.sqlite3'])
    def test_the_history_that_is_there_is_the_one_read(
            self, shell, os_environ, tmpdir, name):
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        tmpdir.mkdir('nushell').join(name).write('')
        assert shell._get_history_file_name().endswith(name)

    def test_the_newest_wins_when_both_are_there(self, shell, os_environ,
                                                 tmpdir):
        """Switching `file_format` leaves the other file behind rather than
        removing it, so the stale one must not be the one that is read."""
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        directory = tmpdir.mkdir('nushell')
        stale = directory.join('history.txt')
        stale.write('')
        os.utime(str(stale), (1, 1))
        current = directory.join('history.sqlite3')
        current.write('')
        assert shell._get_history_file_name().endswith('history.sqlite3')

    def test_get_history_from_plain_text(self, shell, os_environ, tmpdir):
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        tmpdir.mkdir('nushell').join('history.txt').write_text(
            u'ls\ngit status\n', 'utf-8')
        assert list(shell.get_history()) == ['ls', 'git status']

    def test_get_history_from_sqlite(self, shell, os_environ, tmpdir):
        """The database reedline writes when `file_format` is `sqlite`."""
        import sqlite3

        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        path = str(tmpdir.mkdir('nushell').join('history.sqlite3'))
        connection = sqlite3.connect(path)
        connection.execute(
            'CREATE TABLE history (id integer primary key autoincrement,'
            ' command_line text not null, start_timestamp integer,'
            ' session_id integer, hostname text, cwd text,'
            ' duration_ms integer, exit_status integer, more_info text)')
        connection.executemany(
            'INSERT INTO history (command_line) VALUES (?)',
            [('ls',), ('git status',)])
        connection.commit()
        connection.close()

        assert list(shell.get_history()) == ['ls', 'git status']

    def test_get_history_survives_a_damaged_database(self, shell, os_environ,
                                                     tmpdir):
        """Two rules do without history; none of them may lose a correction."""
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        tmpdir.mkdir('nushell').join('history.sqlite3').write('not a database')
        assert list(shell.get_history()) == []

    def test_get_history_without_a_history_at_all(self, shell, os_environ,
                                                  tmpdir):
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        assert list(shell.get_history()) == []

    def test_how_to_configure(self, shell, os_environ, tmpdir):
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        configuration = shell.how_to_configure()
        assert configuration.path.endswith(
            os.path.join('nushell', 'config.nu'))
        assert 'def bleep' in configuration.content
        assert not configuration.can_configure_automatically

    def test_info(self, shell, Popen):
        Popen.return_value.stdout.read.return_value = b'0.108.0\n'
        assert shell.info() == 'Nushell 0.108.0'


class TestWithNowhereToLook(object):
    """No `APPDATA` and no home directory Windows will admit to.

    `os.path.expanduser` hands the `~` back rather than raising, so this used to
    produce `~\\nushell\\history.sqlite3` -- a path nobody can read and, worse,
    advice to edit a file called `~`.

    """

    @pytest.fixture
    def shell(self):
        return Nushell()

    @pytest.fixture(autouse=True)
    def no_home(self, os_environ, monkeypatch):
        monkeypatch.setattr('sys.platform', 'win32')
        monkeypatch.setattr('os.name', 'nt')
        # What Windows does when it cannot work out where home is.
        monkeypatch.setattr('os.path.expanduser', lambda path: path)

    def test_no_place_is_named_at_all(self, shell):
        assert shell._config_dirs() == []
        assert shell._config_dir() is None

    def test_no_tilde_path_is_offered_as_the_history(self, shell):
        assert shell._get_history_file_name() == ''
        assert list(shell.get_history()) == []

    def test_the_advice_is_to_ask_nushell(self, shell):
        configuration = shell.how_to_configure()
        assert '~' not in configuration.path
        assert '$nu.default-config-dir' in configuration.path
        assert not configuration.can_configure_automatically
        assert 'def bleep' in configuration.content

    def test_xdg_still_answers_when_it_is_set(self, shell, os_environ, tmpdir):
        """Nothing to expand there, so it is usable even with no home."""
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        assert shell._config_dirs() == [os.path.join(str(tmpdir), 'nushell')]
