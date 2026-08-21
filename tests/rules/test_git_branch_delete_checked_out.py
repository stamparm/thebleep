import pytest
from thebleep.rules import git_branch_delete_checked_out
from thebleep.rules.git_branch_delete_checked_out import match, get_new_command
from thebleep.types import Command


# git 2.45 and older said "Cannot delete branch 'x' checked out at";
# 2.46 and newer say "cannot delete branch 'x' used by worktree at". Only the
# first was matched, so the rule went dead on current git -- and with it dead,
# `git_main_master` answered instead and `git branch -d master` became
# `git branch -d main`, deleting a branch nobody had named. Captured from git
# 2.30.2 and 2.39.5 (old) and 2.47.3 (new).
@pytest.fixture(params=[
    "error: Cannot delete branch 'foo' checked out at '/bar/foo'",
    "error: cannot delete branch 'foo' used by worktree at '/bar/foo'",
])
def output(request):
    return request.param


@pytest.fixture(autouse=True)
def default_branch(mocker):
    """Answers as a repository whose default branch is `master` would."""
    return mocker.patch.object(git_branch_delete_checked_out, '_git',
                               return_value='origin/master')


@pytest.mark.parametrize("script", ["git branch -d foo", "git branch -D foo"])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize("script", ["git branch -d foo", "git branch -D foo"])
def test_not_match(script):
    assert not match(Command(script, "Deleted branch foo (was a1b2c3d)."))


@pytest.mark.parametrize(
    "script, new_command",
    [
        ("git branch -d foo", "git checkout master && git branch -D foo"),
        ("git branch -D foo", "git checkout master && git branch -D foo"),
    ],
)
def test_get_new_command(script, new_command, output):
    assert get_new_command(Command(script, output)) == new_command


@pytest.mark.usefixtures('no_memoize')
def test_the_repositorys_own_default_branch_is_used(output, default_branch):
    """Checking out `master` fails in a repository that has never had one."""
    default_branch.return_value = 'origin/trunk'
    assert get_new_command(Command('git branch -d foo', output)) \
        == 'git checkout trunk && git branch -D foo'


@pytest.mark.usefixtures('no_memoize')
@pytest.mark.parametrize('answers, expected', [
    # No remote HEAD to ask, so whichever of the usual names is really there.
    ({'refs/heads/main': 'abc123'}, 'main'),
    ({'refs/heads/master': 'abc123'}, 'master'),
    # Neither, and nothing else to go on: the old guess is as good as any.
    ({}, 'master'),
])
def test_falling_back_when_there_is_no_remote(answers, expected, output,
                                              default_branch, mocker):
    def answer(*arguments):
        if arguments[0] == 'symbolic-ref':
            return ''
        return answers.get(arguments[-1], '')

    default_branch.side_effect = answer
    assert get_new_command(Command('git branch -d foo', output)) \
        == 'git checkout {} && git branch -D foo'.format(expected)


@pytest.mark.usefixtures('no_memoize')
def test_git_not_being_there_is_not_fatal(mocker, output):
    # `tool_output` answers `''` for every way a program can fail to answer --
    # not installed, not finished in time, exited non-zero -- so a rule sees
    # one thing instead of three exceptions.
    mocker.patch.object(git_branch_delete_checked_out, 'tool_output',
                        return_value='')
    assert get_new_command(Command('git branch -d foo', output)) \
        == 'git checkout master && git branch -D foo'
