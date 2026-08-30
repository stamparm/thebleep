# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.make_no_target import get_new_command, match
from thebleep.types import Command


# Captured from GNU Make 4.3 with a Makefile declaring `build` and `test`.
OUTPUT = "make: *** No rule to make target 'buld'.  Stop."


@pytest.fixture
def project(tmpdir, monkeypatch):
    tmpdir.join('Makefile').write(
        'build:\n\t@printf built\n\n'
        'test:\n\t@printf tested\n')
    monkeypatch.chdir(tmpdir)
    return tmpdir


def test_match_is_limited_to_make(project):
    assert match(Command('make buld', OUTPUT))
    assert not match(Command('nmake buld', OUTPUT))


def test_declared_target_is_suggested(project):
    assert get_new_command(Command('make buld', OUTPUT)) == ['make build']


def test_unreadable_project_metadata_abstains(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    assert get_new_command(Command('make buld', OUTPUT)) == []


def test_target_names_are_quoted(project):
    project.join('Makefile').write('build&touch:\n\t@true\n')
    output = "make: *** No rule to make target 'buil&touch'.  Stop."
    assert get_new_command(Command('make buil&touch', output)) == [
        "make 'build&touch'"]
