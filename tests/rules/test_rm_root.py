import pytest
from thebleep.rules.rm_root import match, get_new_command
from thebleep.types import Command

OUTPUT = ("rm: it is dangerous to operate recursively on '/'\n"
          "rm: use --no-preserve-root to override this failsafe")


def test_match():
    assert match(Command('rm -rf /', OUTPUT))


def test_sudo_rm_still_matches():
    assert match(Command('sudo rm -rf /', OUTPUT))


@pytest.mark.parametrize('script', [
    'echo rm /',
    'git rm /',
    'python rm /',
])
def test_words_in_another_command_are_not_a_root_removal(script):
    assert not match(Command(script, OUTPUT))


@pytest.mark.parametrize('command', [
    Command('ls', OUTPUT),
    Command('rm --no-preserve-root /', OUTPUT),
    Command('rm -rf /', '')])
def test_not_match(command):
    assert not match(command)


def test_get_new_command():
    assert (get_new_command(Command('rm -rf /', ''))
            == 'rm -rf / --no-preserve-root')
