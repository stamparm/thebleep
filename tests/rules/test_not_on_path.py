# -*- encoding: utf-8 -*-

"""A program that exists under the name typed, somewhere PATH does not reach."""

import os

import pytest

from thebleep.rules import not_on_path
from thebleep.rules.not_on_path import get_new_command, match
from thebleep.types import Command

# What the shells print; dash 0.5.12, bash 5.2, zsh 5.9, fish 4.0.2 and
# PowerShell 7, each asked for a program that is not there.
DASH = 'sh: 1: cargo: not found'
BASH = 'bash: cargo: command not found'
ZSH = 'zsh: command not found: cargo'
FISH = 'fish: Unknown command: cargo'
PWSH = ("cargo: The term 'cargo' is not recognized as a name of a cmdlet, "
        'function, script file, or executable program.')


def executable(directory, name):
    """An executable called `name` in `directory`, as the platform spells one:
    a mode bit on POSIX, an `.exe` suffix on Windows."""
    path = directory.ensure(name + ('.exe' if os.name == 'nt' else ''))
    path.chmod(0o755)
    return str(path)


def exe(name):
    """`name` as the platform spells an executable file."""
    return name + ('.exe' if os.name == 'nt' else '')


def quoted(path):
    """How the suggestion spells `path`: through the shell's own quoting, which
    leaves a plain POSIX path alone and quotes a Windows one for its
    backslashes."""
    from thebleep.shells import shell

    return shell.quote(path)


@pytest.fixture
def machine(tmpdir, os_environ, monkeypatch, mocker):
    """A home, a PATH that reaches none of the usual places, and a cwd."""
    home = tmpdir.mkdir('home')
    on_path = tmpdir.mkdir('onpath')
    os_environ['HOME'] = str(home)
    os_environ['USERPROFILE'] = str(home)
    os_environ['PATH'] = str(on_path)
    work = tmpdir.mkdir('work')
    monkeypatch.chdir(work)
    # `which` is memoized for the process; the machine here is a new one.
    from thebleep import utils

    monkeypatch.setattr(utils.memoize, 'disabled', True)
    return tmpdir


@pytest.mark.parametrize('output', [DASH, BASH, ZSH, FISH, PWSH, None])
def test_match_when_the_program_is_missing(machine, output):
    assert match(Command('cargo build', output))


def test_not_match_when_it_is_on_path(machine):
    executable(machine.join('onpath'), 'cargo')
    assert not match(Command('cargo build', BASH))


@pytest.mark.parametrize('script, output', [
    ('./cargo build', BASH),
    ('cargo build', 'error: could not compile'),
    ('cargo build', 'bash: rustc: command not found'),
    ('', BASH),
])
def test_not_match(machine, script, output):
    assert not match(Command(script, output))


class TestInstallers(object):
    def test_the_full_path_and_the_export(self, machine):
        cargo = executable(machine.join('home').mkdir('.cargo').mkdir('bin'),
                           'cargo')
        got = get_new_command(Command('cargo build --release', BASH))
        assert got == [
            '{} build --release'.format(quoted(cargo)),
            'export PATH={}:"$PATH" && cargo build --release'.format(
                quoted(os.path.dirname(cargo)))]
        assert got[0].confidence == 0.9
        assert got[0].evidence == (
            'cargo is installed at {}, which is not on PATH'.format(cargo),)
        assert got[1].evidence[1] == 'puts {} on PATH for this shell'.format(
            os.path.dirname(cargo))

    def test_a_version_managers_directory_is_globbed(self, machine):
        node = executable(
            machine.join('home').mkdir('.nvm').mkdir('versions').mkdir('node')
            .mkdir('v22.1.0').mkdir('bin'), 'node')
        assert get_new_command(Command('node -v', ZSH.replace(
            'cargo', 'node')))[0] == '{} -v'.format(quoted(node))

    def test_a_directory_already_on_path_is_not_the_answer(
            self, machine, os_environ):
        directory = machine.join('home').mkdir('.local').mkdir('bin')
        executable(directory, 'tool')
        os_environ['PATH'] = str(directory)
        # It is on PATH, so `which` finds it and the rule does not match at
        # all; and even asked directly, that directory is not offered.
        assert not match(Command('tool', None))
        assert not_on_path._found('tool') == []

    def test_nothing_anywhere(self, machine):
        assert get_new_command(Command('cargo build', BASH)) == []

    @pytest.mark.skipif(os.name == 'nt',
                        reason='Windows has no execute bit to take away')
    def test_a_directory_that_is_not_executable_does_not_count(self, machine):
        machine.join('home').mkdir('.cargo').mkdir('bin').ensure('cargo')
        os.chmod(str(machine.join('home', '.cargo', 'bin', 'cargo')), 0o644)
        assert get_new_command(Command('cargo build', BASH)) == []

    def test_a_wrapper_in_front_is_kept(self, machine):
        cargo = executable(machine.join('home').mkdir('.cargo').mkdir('bin'),
                           'cargo')
        got = get_new_command(Command('RUST_LOG=debug cargo test', BASH.replace(
            'cargo', 'cargo')))
        assert got[0] == 'RUST_LOG=debug {} test'.format(quoted(cargo))


class TestProjects(object):
    def test_node_modules_bin_nearest_first(self, machine):
        work = machine.join('work')
        executable(work.mkdir('node_modules').mkdir('.bin'), 'prettier')
        got = get_new_command(Command('prettier --check .', ZSH.replace(
            'cargo', 'prettier')))
        assert got == ['./node_modules/.bin/{} --check .'.format(exe('prettier'))]
        assert got[0].evidence == (
            'prettier is in this project at ./node_modules/.bin/{}'.format(
                exe('prettier')),)

    def test_a_venv_in_the_parent(self, machine, monkeypatch):
        work = machine.join('work')
        pytest_bin = executable(work.mkdir('.venv').mkdir('bin'), 'pytest')
        inside = work.mkdir('tests')
        monkeypatch.chdir(inside)
        got = get_new_command(Command('pytest -q', FISH.replace(
            'cargo', 'pytest')))
        assert got == ['../.venv/bin/{} -q'.format(exe('pytest'))]
        assert os.path.samefile(
            pytest_bin, str(inside.join('..', '.venv', 'bin', exe('pytest'))))

    def test_the_search_stops_at_the_repository_root(self, machine,
                                                     monkeypatch):
        work = machine.join('work')
        executable(work.mkdir('node_modules').mkdir('.bin'), 'prettier')
        repo = work.mkdir('other-repo')
        repo.mkdir('.git')
        monkeypatch.chdir(repo)
        assert get_new_command(Command('prettier .', BASH.replace(
            'cargo', 'prettier'))) == []

    def test_the_project_beats_the_home(self, machine):
        work = machine.join('work')
        executable(work.mkdir('.venv').mkdir('bin'), 'pytest')
        executable(machine.join('home').mkdir('.local').mkdir('bin'), 'pytest')
        got = get_new_command(Command('pytest', BASH.replace('cargo', 'pytest')))
        assert got[0] == './.venv/bin/{}'.format(exe('pytest'))
        assert len(got) == 3


def test_a_path_with_shell_syntax_in_it_is_quoted(tmpdir, os_environ,
                                                  monkeypatch):
    """A home directory is whatever the machine calls it."""
    from thebleep import utils

    monkeypatch.setattr(utils.memoize, 'disabled', True)
    home = tmpdir.mkdir('my $(touch pwned) home')
    os_environ['HOME'] = str(home)
    os_environ['USERPROFILE'] = str(home)
    os_environ['PATH'] = str(tmpdir.mkdir('onpath'))
    monkeypatch.chdir(tmpdir.mkdir('work'))
    tool = executable(home.mkdir('.cargo').mkdir('bin'), 'tool')
    got = get_new_command(Command('tool', BASH.replace('cargo', 'tool')))
    assert got[0] == "'{}'".format(tool)
    assert got[1].startswith("export PATH='{}':\"$PATH\" && tool".format(
        os.path.dirname(tool)))
    assert "'" + os.path.dirname(tool) + "'" == quoted(os.path.dirname(tool))


@pytest.mark.parametrize('shell_module, klass, expected', [
    ('generic', 'Generic', 'export PATH=/opt/tools/bin:"$PATH"'),
    ('bash', 'Bash', 'export PATH=/opt/tools/bin:"$PATH"'),
    ('zsh', 'Zsh', 'export PATH=/opt/tools/bin:"$PATH"'),
    ('fish', 'Fish', 'set -gx PATH /opt/tools/bin $PATH'),
    ('tcsh', 'Tcsh', 'setenv PATH /opt/tools/bin:$PATH'),
    ('powershell', 'Powershell',
     "$env:PATH = '/opt/tools/bin' + [IO.Path]::PathSeparator + $env:PATH"),
    ('nushell', 'Nushell', '$env.PATH = ($env.PATH | prepend /opt/tools/bin)'),
])
def test_every_shell_can_put_a_directory_on_path(shell_module, klass, expected):
    import importlib

    module = importlib.import_module('thebleep.shells.' + shell_module)
    assert getattr(module, klass)().put_on_path('/opt/tools/bin') == expected


def test_a_directory_with_a_space_is_quoted_for_the_shell():
    from thebleep.shells.generic import Generic
    from thebleep.shells.fish import Fish

    assert Generic().put_on_path('/opt/my tools/bin') == \
        "export PATH='/opt/my tools/bin':\"$PATH\""
    assert Fish().put_on_path('/opt/my tools/bin') == \
        "set -gx PATH '/opt/my tools/bin' $PATH"


def test_quoting_in_front_of_the_program_is_kept(machine):
    """`FOO="a b" prettier` used to come back as `FOO="a ./…/prettier`."""
    executable(machine.join('work').mkdir('node_modules').mkdir('.bin'),
               'prettier')
    got = get_new_command(Command(
        'FOO="a b" prettier \'x;echo pwned\'',
        BASH.replace('cargo', 'prettier')))
    assert got[0] == 'FOO="a b" ./node_modules/.bin/{} \'x;echo pwned\''.format(
        exe('prettier'))
