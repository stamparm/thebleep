# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.poetry_command_not_found import get_new_command, match
from thebleep.types import Command


# Captured from Poetry 2.4.2 with a `server` script in pyproject.toml.
OUTPUT = 'Command not found: servr'


@pytest.fixture
def project(tmpdir, monkeypatch):
    tmpdir.join('pyproject.toml').write(
        '[tool.poetry]\nname = "demo"\nversion = "0.1.0"\n\n'
        '[tool.poetry.scripts]\nserver = "demo:main"\n')
    monkeypatch.chdir(tmpdir)
    return tmpdir


def test_match_requires_poetry_run(project):
    assert match(Command('poetry run servr', OUTPUT))
    assert not match(Command('poetry install servr', OUTPUT))


def test_declared_script_is_suggested(project):
    assert get_new_command(Command('poetry run servr', OUTPUT)) == [
        'poetry run server']


def test_unreadable_project_metadata_abstains(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    assert get_new_command(Command('poetry run servr', OUTPUT)) == []
