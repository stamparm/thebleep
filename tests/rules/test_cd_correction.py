import pytest
from thebleep.rules.cd_correction import get_new_command, match
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command('cd foo', 'cd: foo: No such file or directory'),
    Command('cd foo/bar/baz',
            'cd: foo: No such file or directory'),
    Command('cd foo/bar/baz', 'cd: can\'t cd to foo/bar/baz'),
    Command('cd /foo/bar/', 'cd: The directory "/foo/bar/" does not exist')])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('cd foo', ''), Command('', '')])
def test_not_match(command):
    assert not match(command)


def test_environment_assignment_is_preserved(tmp_path, monkeypatch):
    (tmp_path / 'foo').mkdir()
    monkeypatch.chdir(str(tmp_path))
    command = Command('CDPATH= cd fop',
                      'cd: fop: No such file or directory')

    assert get_new_command(command) == 'CDPATH= cd foo'


def test_a_relative_destination_stays_relative(tmp_path, monkeypatch):
    """`cd Documnets` came back as `cd /home/me/projects/Documents`."""
    tmp_path.joinpath('Documents').mkdir()
    monkeypatch.chdir(str(tmp_path))
    command = Command('cd Documnets',
                      'cd: Documnets: No such file or directory')
    assert get_new_command(command) == 'cd Documents'


def test_dots_in_a_relative_destination_are_kept(tmp_path, monkeypatch):
    tmp_path.joinpath('Documents').mkdir()
    tmp_path.joinpath('here').mkdir()
    monkeypatch.chdir(str(tmp_path.joinpath('here')))
    command = Command('cd ../Documnets',
                      'cd: ../Documnets: No such file or directory')
    assert get_new_command(command) == 'cd ../Documents'


def test_an_absolute_destination_stays_absolute(tmp_path, monkeypatch):
    tmp_path.joinpath('Documents').mkdir()
    monkeypatch.chdir(str(tmp_path))
    # Forward slashes, which Windows takes too: the generic shell splits the
    # script the POSIX way, and a backslash there is an escape.
    typo = tmp_path.joinpath('Documnets').as_posix()
    command = Command('cd ' + typo,
                      'cd: ' + typo + ': No such file or directory')
    assert get_new_command(command) == 'cd ' + tmp_path.joinpath(
        'Documents').as_posix()
