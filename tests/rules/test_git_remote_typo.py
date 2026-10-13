import pytest
from thebleep.rules import git_remote_typo
from thebleep.rules.git_remote_typo import get_new_command, match
from thebleep.types import Command

# git 2.53.0 (debian:testing).
NOT_A_REMOTE = '''fatal: 'orign' does not appear to be a git repository
fatal: Could not read from remote repository.

Please make sure you have the correct access rights
and the repository exists.
'''
NO_REF = "fatal: couldn't find remote ref mian\n"


@pytest.fixture(autouse=True)
def git(mocker):
    def tool_lines(arguments, *args, **kwargs):
        if arguments == ['git', 'remote']:
            return ['origin', 'upstream']
        if '-r' not in arguments:
            return ['master', 'feature']
        return ['origin/main', 'origin/feature', 'upstream/main', 'origin']
    return mocker.patch.object(git_remote_typo, 'tool_lines',
                               side_effect=tool_lines)


@pytest.mark.parametrize('script, output, fixed', [
    ('git push orign main', NOT_A_REMOTE, 'git push origin main'),
    ('git fetch upstrem', NOT_A_REMOTE.replace('orign', 'upstrem'),
     'git fetch upstream'),
    ('git pull origin mian', NO_REF, 'git pull origin main'),
    ('git pull origin featur', NO_REF.replace('mian', 'featur'),
     'git pull origin feature'),
    # Was `git commit -m "Initial commit" && git push origin mastr`.
    ('git push origin mastr', 'error: src refspec mastr does not match any\n'
     "error: failed to push some refs to '/tmp/bare'\n", 'git push origin master')])
def test_a_slip_in_a_name_git_already_has(script, output, fixed):
    command = Command(script, output)
    assert match(command)
    assert get_new_command(command)[0] == fixed


def test_nothing_near_is_nothing_offered():
    command = Command('git push nowhere main',
                      NOT_A_REMOTE.replace('orign', 'nowhere'))
    assert get_new_command(command) == []


def test_not_a_transfer():
    assert not match(Command('git log orign', NOT_A_REMOTE))
