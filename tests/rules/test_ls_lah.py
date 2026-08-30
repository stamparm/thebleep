from thebleep.rules.ls_lah import match, get_new_command
from thebleep.types import Command


def test_match():
    assert match(Command('ls', ''))
    assert match(Command('ls file.py', ''))
    assert match(Command('ls /opt', ''))
    assert match(Command("ls 'dir/ls -file'", ''))
    assert not match(Command('ls -lah /opt', ''))
    assert not match(Command('pacman -S binutils', ''))
    assert not match(Command('lsof', ''))


def test_not_on_a_failure():
    """`ls` saying the argument is not there is not a listing that hid
    anything -- more flags were offered to a command that had just failed,
    and rerunning it fails again."""
    assert not match(Command(
        'ls /nonexistent-dir-xyz',
        "ls: cannot access '/nonexistent-dir-xyz': "
        'No such file or directory\n'))


def test_get_new_command():
    assert get_new_command(Command('ls file.py', '')) == 'ls -lah file.py'
    assert get_new_command(Command('ls', '')) == 'ls -lah'
    assert get_new_command(Command('LS_COLOR=1 ls file.py', '')) == \
        'LS_COLOR=1 ls -lah file.py'
