from unittest.mock import patch
from thebleep.rules.has_exists_script import match, get_new_command
from thebleep.types import Command


def test_match():
    with patch('os.path.exists', return_value=True):
        assert match(Command('main', 'main: command not found'))
        assert match(Command('main --help',
                             'main: command not found'))
        assert not match(Command('main', ''))

    with patch('os.path.exists', return_value=False):
        assert not match(Command('main', 'main: command not found'))


def test_get_new_command():
    with patch('os.access', return_value=True):
        assert get_new_command(Command('main --help', '')) == './main --help'


def test_environment_assignment_is_preserved():
    with patch('os.access', return_value=True):
        assert (get_new_command(Command('PATH=/tmp main --help', ''))
                == 'PATH=/tmp ./main --help')


def test_fish_and_a_file_that_is_not_executable(tmpdir, monkeypatch):
    """fish 4.0 says `Unknown command: script.sh`; and `./script.sh` on a
    file without the bit only trades that for `permission denied`."""
    monkeypatch.chdir(tmpdir)
    tmpdir.join('script.sh').write('#!/bin/sh\necho hi\n')
    command = Command('script.sh', 'fish: Unknown command: script.sh\n')
    assert match(command)
    with patch('os.access', return_value=False):
        assert get_new_command(command) == 'chmod +x script.sh && ./script.sh'


def test_a_path_is_already_a_path(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)
    tmpdir.join('script.sh').write('#!/bin/sh\n')
    assert not match(Command('./script.sh', "fish: Unknown command. "
                             "'./script.sh' exists but is not an executable "
                             "file.\n"))
