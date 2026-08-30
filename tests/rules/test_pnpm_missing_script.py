# -*- encoding: utf-8 -*-

import json

from thebleep.rules.pnpm_missing_script import get_new_command, match
from thebleep.types import Command


# Captured from pnpm 11.24.0 with a package.json script named `build`.
NO_SCRIPT = ('[ERR_PNPM_NO_SCRIPT] Missing script: buld\n\n'
             'Command "buld" not found. Did you mean "pnpm run build"?')
NO_COMMAND = ('[ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL] Command "buld" not found\n'
              'Did you mean "pnpm build"?')


def test_match_is_limited_to_pnpm():
    assert match(Command('pnpm run buld', NO_SCRIPT))
    assert match(Command('pnpm buld', NO_COMMAND))
    assert not match(Command('npm run buld', NO_SCRIPT))


def test_project_script_is_suggested(tmpdir, monkeypatch):
    tmpdir.join('package.json').write(json.dumps(
        {'scripts': {'build': 'echo built', 'test': 'echo tested'}}))
    monkeypatch.chdir(tmpdir)

    assert get_new_command(Command('pnpm run buld', NO_SCRIPT)) == [
        'pnpm run build']


def test_pnpm_native_hint_works_without_a_manifest(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)

    assert get_new_command(Command('pnpm buld', NO_COMMAND)) == ['pnpm build']


def test_unreadable_project_metadata_keeps_native_hint_only(tmpdir,
                                                            monkeypatch):
    monkeypatch.chdir(tmpdir)
    tmpdir.join('package.json').write('{"scripts":')

    assert get_new_command(Command('pnpm run buld', NO_SCRIPT)) == [
        'pnpm run build']
