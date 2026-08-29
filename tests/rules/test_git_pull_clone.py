import pytest
from thebleep.rules.git_pull_clone import match, get_new_command
from thebleep.types import Command


git_err = '''
fatal: Not a git repository (or any parent up to mount point /home)
Stopping at filesystem boundary (GIT_DISCOVERY_ACROSS_FILESYSTEM not set).
'''


@pytest.mark.parametrize('command', [
    Command('git pull git@github.com:mcarton/thebleep.git', git_err)])
def test_match(command):
    assert match(command)


def test_another_git_command_does_not_become_a_clone():
    assert not match(Command(
        'git status',
        git_err))


def test_current_git_wording_is_accepted():
    output = ('fatal: not a git repository (or any parent up to mount point /)\n'
              'Stopping at filesystem boundary '
              '(GIT_DISCOVERY_ACROSS_FILESYSTEM not set).\n')
    assert match(Command('git pull git@github.com:mcarton/thebleep.git', output))


def test_global_options_still_find_pull():
    command = Command(
        'git -C worktree pull git@github.com:mcarton/thebleep.git',
        git_err)
    assert match(command)
    assert get_new_command(command) == \
        'git -C worktree clone git@github.com:mcarton/thebleep.git'


@pytest.mark.parametrize('command, output', [
    (Command('git pull git@github.com:mcarton/thebleep.git', git_err), 'git clone git@github.com:mcarton/thebleep.git')])
def test_get_new_command(command, output):
    assert get_new_command(command) == output
