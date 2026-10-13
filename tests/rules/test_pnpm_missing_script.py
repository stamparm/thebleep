# -*- encoding: utf-8 -*-

import json

import pytest

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


@pytest.mark.parametrize('output', [
    ' ERR_PNPM_NO_SCRIPT  Missing script: buld\n\n'
    'Command "buld" not found. Did you mean "pnpm run build"?\n',
    '[ERR_PNPM_NO_SCRIPT] Missing script: buld\n\n'
    'Command "buld" not found. Did you mean "pnpm run build"?\n',
    'Error: ERR_PNPM_NO_SCRIPT\n\n  × Missing script: buld\n'
    '  help: Command "buld" not found.\n'])
def test_every_current_pnpm(output, mocker):
    """pnpm 9.15.9 and 10.34.7, 11.28.5, 12.11.2 -- three wordings."""
    mocker.patch('thebleep.project_context.package_scripts',
                 return_value=['build', 'test'])
    command = Command('pnpm run buld', output)
    assert match(command)
    assert get_new_command(command)[0] == 'pnpm run build'


def test_one_of_pnpms_own_commands(mocker):
    """pnpm 12: `pnpm instal` names no candidate at all."""
    mocker.patch('thebleep.project_context.package_scripts',
                 return_value=['build'])
    output = ('Error: ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL\n\n'
              '  × Command "instal" not found\n')
    command = Command('pnpm instal', output)
    assert match(command)
    assert get_new_command(command)[0] == 'pnpm install'
