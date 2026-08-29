# -*- coding: utf-8 -*-

import marshal
import os
import stat

import pytest

from thebleep import cachefile
from thebleep.system import Path


@pytest.fixture
def cache_home(tmpdir, monkeypatch):
    directory = Path(str(tmpdir))
    monkeypatch.setattr(cachefile, 'directory', lambda: directory)
    return tmpdir


@pytest.mark.skipif(not hasattr(os, 'geteuid'),
                    reason='Windows has no POSIX mode to check')
def test_cache_files_are_private(cache_home):
    cachefile.save('private', (), 'value')

    path = cache_home.join('private.cache')
    assert stat.S_IMODE(os.stat(str(path)).st_mode) == 0o600


def test_failed_exclusive_create_does_not_remove_an_existing_temp(
        cache_home, mocker):
    open_file = mocker.patch.object(
        cachefile.os, 'open', side_effect=FileExistsError())
    unlink = mocker.patch.object(cachefile.os, 'unlink')

    assert cachefile.save('probe', (), 'value') == 'value'
    open_file.assert_called_once()
    assert not unlink.called


@pytest.mark.skipif(not hasattr(os, 'O_NOFOLLOW'),
                    reason='platform has no no-follow open flag')
def test_load_rejects_a_symlinked_cache(cache_home):
    target = cache_home.join('target')
    with target.open('wb') as handle:
        marshal.dump({'format': cachefile.FORMAT, 'fingerprint': (),
                      'value': 'untrusted'}, handle)
    os.symlink(str(target), str(cache_home.join('linked.cache')))

    assert cachefile.load('linked', ()) is None
