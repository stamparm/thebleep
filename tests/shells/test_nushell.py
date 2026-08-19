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

    def test_history_file_prefers_the_one_that_exists(self, shell, mocker,
                                                      os_environ, tmpdir):
        os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
        directory = tmpdir.mkdir('nushell')
        assert shell._get_history_file_name().endswith('history.sqlite3')
        directory.join('history.txt').write('')
        assert shell._get_history_file_name().endswith('history.txt')

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
