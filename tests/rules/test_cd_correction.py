import pytest
from thebleep.rules.cd_correction import get_new_command, match
from thebleep.shells import shell
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

    assert get_new_command(command) == \
        'CDPATH= cd {}'.format(shell.quote(str(tmp_path / 'foo')))
