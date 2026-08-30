# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.just_no_recipe import get_new_command, match
from thebleep.types import Command


# Captured from just 1.58.0 with a Justfile declaring `build` and `test`.
OUTPUT = ('error: justfile does not contain recipe `buld`\n'
          'Did you mean `build`?')


@pytest.fixture
def project(tmpdir, monkeypatch):
    tmpdir.join('Justfile').write(
        'build:\n\t@printf built\n\n'
        'test:\n\t@printf tested\n')
    monkeypatch.chdir(tmpdir)
    return tmpdir


def test_match_is_limited_to_just(project):
    assert match(Command('just buld', OUTPUT))
    assert not match(Command('justx buld', OUTPUT))


def test_declared_recipe_is_suggested(project):
    assert get_new_command(Command('just buld', OUTPUT)) == ['just build']


def test_unreadable_project_metadata_abstains(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    assert get_new_command(Command('just buld', OUTPUT)) == []


def test_alias_is_suggested(project):
    project.join('Justfile').write('alias b := build\n')
    output = 'error: Justfile does not contain recipe `a`'
    assert get_new_command(Command('just a', output)) == ['just b']
