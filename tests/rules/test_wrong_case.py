# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.wrong_case import get_new_command, match
from thebleep.types import Command


@pytest.fixture(autouse=True)
def executables(mocker):
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
        return_value=['git', 'ls', 'cat'])
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.shell'
        '.get_builtin_commands', return_value=['cd'])
    mocker.patch('thebleep.vocabulary.subcommands',
                 side_effect=lambda tool, prefix=(): {
                     'git': ['status', 'commit']}.get(tool, []))


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script, fixed', [
    ('GIT STATUS', 'git status'),               # caps lock: all of it
    ('LS -LA', 'ls -la'),
    ('GIT status', 'git status'),               # Shift: the word alone
    ('Git status', 'git status'),
    ('LS -la /TMP/X', 'ls -la /TMP/X'),
    ('git STATUS', 'git status'),
    ('git Commit -m "Fix It"', 'git commit -m "Fix It"'),
    ('CD ..', 'cd ..'),
])
def test_the_case_is_put_right(script, fixed):
    command = Command(script, '')
    assert match(command)
    assert get_new_command(command) == fixed


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('script', [
    'git status',
    'cat README',                # an argument in capitals is an argument
    'git README',                # not a subcommand git documents
    'FOO bar',                   # nothing called foo either
    'ls',
])
def test_nothing_else(script):
    assert not match(Command(script, ''))
