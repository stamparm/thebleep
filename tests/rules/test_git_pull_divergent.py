import pytest
from thebleep.rules.git_pull_divergent import get_new_command, match
from thebleep.types import Command

# git 2.53.0 (debian:testing), `git pull origin master` on a diverged branch.
OUTPUT = '''From /tmp/bare
 * branch            master     -> FETCH_HEAD
hint: You have divergent branches and need to specify how to reconcile them.
hint: You can do so by running one of the following commands sometime before
hint: your next pull:
hint:
hint:   git config pull.rebase false  # merge
hint:   git config pull.rebase true   # rebase
hint:   git config pull.ff only       # fast-forward only
fatal: Need to specify how to reconcile divergent branches.
'''


@pytest.mark.parametrize('script, first', [
    ('git pull', 'git pull --rebase'),
    ('git pull origin master', 'git pull --rebase origin master'),
    ('git -C repo pull', 'git -C repo pull --rebase')])
def test_the_three_answers_git_names(script, first):
    command = Command(script, OUTPUT)
    assert match(command)
    fixed = get_new_command(command)
    assert fixed[0] == first
    assert [option for option in ('--rebase', '--no-rebase', '--ff-only')
            if any(option in line for line in fixed)] == [
        '--rebase', '--no-rebase', '--ff-only']


def test_not_a_pull():
    assert not match(Command('git config pull.rebase', OUTPUT))
    assert not match(Command('git pull', 'Already up to date.'))
