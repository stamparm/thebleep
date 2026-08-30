from thebleep.rules.ls_all import match, get_new_command
from thebleep.types import Command


def test_match():
    assert match(Command('ls', ''))
    assert not match(Command('ls', 'file.py\n'))


def test_get_new_command():
    assert get_new_command(Command('ls empty_dir', '')) == 'ls -A empty_dir'
    assert get_new_command(Command('ls', '')) == 'ls -A'
    assert get_new_command(Command('LS_COLOR=1 ls empty_dir', '')) == \
        'LS_COLOR=1 ls -A empty_dir'
