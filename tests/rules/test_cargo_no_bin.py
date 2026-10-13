# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.cargo_no_bin import get_new_command, match
from thebleep.types import Command


# Captured from Cargo 1.75.0 with an explicit `server` binary target.
OUTPUT = ('error: no bin target named `servr`\n\n'
          'Did you mean `server`?')


@pytest.fixture
def project(tmpdir, monkeypatch):
    tmpdir.join('Cargo.toml').write(
        '[package]\nname = "demo"\nversion = "0.1.0"\n\n'
        '[[bin]]\nname = "server"\n')
    monkeypatch.chdir(tmpdir)
    return tmpdir


def test_match_requires_bin_mode(project):
    assert match(Command('cargo run --bin servr', OUTPUT))
    assert not match(Command('cargo build servr', OUTPUT))


def test_declared_binary_is_suggested(project):
    assert get_new_command(Command('cargo run --bin servr', OUTPUT)) == [
        'cargo run --bin server']


def test_unreadable_project_metadata_and_no_word_from_cargo_abstains(
        tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    output = 'error: no bin target named `servr`\n'
    assert get_new_command(Command('cargo run --bin servr', output)) == []


def test_cargos_own_suggestion_for_a_default_crate(mocker):
    """cargo 1.85 (debian:trixie), `cargo new app`: no `[[bin]]` table to
    read, and cargo names the target itself."""
    mocker.patch('thebleep.project_context.cargo_bins', return_value=None)
    command = Command('cargo run --bin ap',
                      'error: no bin target named `ap`\n\n\tDid you mean `app`?\n')
    assert match(command)
    assert get_new_command(command) == ['cargo run --bin app']
