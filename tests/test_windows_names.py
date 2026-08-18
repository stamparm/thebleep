# -*- coding: utf-8 -*-

"""Finding a command whose file is not spelled the way anybody types it.

On Windows `ping` is a file called `PING.EXE`, and `pnpm` is `pnpm.cmd`. The
close-match search compared the typo against the file name as it sits on disk,
which is a different word from the one the user meant, so the commonest rule
of all found nothing on the commonest Windows commands.

"""

import os
import pytest
from thebleep import utils

WINDOWS_PATHEXT = '.COM;.EXE;.BAT;.CMD;.VBS;.JS;.WSF;.MSC'
WINDOWS_EXTENSIONS = tuple(WINDOWS_PATHEXT.lower().split(';'))


@pytest.fixture
def windows_names(monkeypatch):
    """The two things that differ about looking up a command on Windows.

    Faked at exactly these two points rather than by setting `os.name`, which
    would also send `pathlib` looking for a `WindowsPath` it cannot build here.

    """
    monkeypatch.setattr(utils, 'CASE_INSENSITIVE_NAMES', True)
    monkeypatch.setattr(utils, '_executable_extensions',
                        lambda: WINDOWS_EXTENSIONS)


@pytest.mark.parametrize('name, expected', [
    ('PING.EXE', 'PING'),
    ('pnpm.cmd', 'pnpm'),
    ('python.exe', 'python'),
    ('activate.bat', 'activate'),
    # Not an executable extension, so it is part of the name.
    ('libcrypto.dll', 'libcrypto.dll'),
    ('my.tool.exe', 'my.tool'),
    ('.gitignore', '.gitignore'),
])
def test_the_extension_windows_lets_you_omit_is_dropped(name, expected):
    assert utils._invocable_name(name, WINDOWS_EXTENSIONS) == expected


def test_pathext_is_read_the_way_windows_writes_it(monkeypatch):
    monkeypatch.setattr(os, 'name', 'nt')
    monkeypatch.setitem(os.environ, 'PATHEXT', WINDOWS_PATHEXT)
    assert utils._executable_extensions() == WINDOWS_EXTENSIONS


def test_nothing_is_dropped_elsewhere(monkeypatch):
    monkeypatch.setattr(os, 'name', 'posix')
    assert utils._executable_extensions() == ()
    assert utils._invocable_name('PING.EXE', ()) == 'PING.EXE'


@pytest.mark.parametrize('typo, expected', [
    ('pingg', 'PING'),
    ('PINGG', 'PING'),
    ('pnmp', 'pnpm'),
    ('pyhton', 'python'),
])
def test_a_typo_finds_the_real_command(typo, expected, windows_names):
    """The names are as `_scan_executables` reports them, and what comes back
    keeps whatever case the file really has."""
    executables = ['PING', 'pnpm', 'python', 'robocopy']
    assert utils.get_close_matches(typo, executables)[0] == expected


def test_case_is_still_significant_on_a_case_sensitive_filesystem(monkeypatch):
    monkeypatch.setattr(utils, 'CASE_INSENSITIVE_NAMES', False)
    assert utils.get_close_matches('PINGG', ['ping']) == []


def test_the_suggested_name_is_not_folded(windows_names):
    """Lowercasing to compare must not lowercase what comes back."""
    assert utils.get_close_matches('robocpy', ['ROBOCOPY']) == ['ROBOCOPY']


def test_scanning_reports_names_as_they_would_be_typed(tmpdir, os_environ,
                                                       windows_names):
    os_environ['XDG_CACHE_HOME'] = str(tmpdir.mkdir('cache'))
    bin_dir = tmpdir.mkdir('bin')
    for name in ('PING.EXE', 'pnpm.cmd', 'notes.txt'):
        bin_dir.join(name).write('')
    os_environ['PATH'] = str(bin_dir)

    # `notes.txt` is not in PATHEXT, so typing `notes` runs nothing and typing
    # `notes.txt` opens an editor. It used to be listed as a command.
    found = utils._scan_executables([str(bin_dir)], ())
    assert sorted(found) == ['PING', 'pnpm']
