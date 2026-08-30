from thebleep.rules.python_command import match, get_new_command
from thebleep.types import Command


def test_match():
    assert match(Command('temp.py', 'Permission denied'))
    assert not match(Command('', ''))


def test_get_new_command():
    assert (get_new_command(Command('./test_sudo.py', ''))
            == 'python ./test_sudo.py')


def test_environment_assignment_is_preserved():
    assert (get_new_command(Command('PYTHONPATH=. ./test_sudo.py', ''))
            == 'PYTHONPATH=. python ./test_sudo.py')
