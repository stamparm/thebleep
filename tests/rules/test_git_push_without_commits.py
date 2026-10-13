import pytest
from thebleep.types import Command
from thebleep.rules.git_push_without_commits import get_new_command, match

# git 2.53, `git log -1` in a repository that was just initialised.
NO_COMMITS = "fatal: your current branch 'master' does not have any commits yet"


@pytest.fixture(autouse=True)
def log(mocker):
    return mocker.patch(
        'thebleep.rules.git_push_without_commits.tool_output',
        return_value=NO_COMMITS)


def test_a_repository_with_commits_is_a_typo_not_an_empty_repository(log):
    """`git push origin mastr` prints the same refspec error, and the answer
    was to commit whatever was staged and push the typo."""
    log.return_value = 'abc1234 Last commit'
    output = 'error: src refspec mastr does not match any'
    assert not match(Command('git push origin mastr', output))


def test_a_probe_that_could_not_run_is_not_evidence(log):
    log.return_value = ''
    output = 'error: src refspec master does not match any'
    assert not match(Command('git push -u origin master', output))


def test_global_options_reach_the_probe(log):
    output = 'error: src refspec master does not match any'
    assert match(Command('git -C worktree push origin master', output))
    assert log.call_args[0][0] == ['git', '-C', 'worktree', 'log', '-1',
                                   '--oneline']


def test_match():
    script = "git push -u origin master"
    output = "error: src refspec master does not match any\nerror: failed to..."
    assert match(Command(script, output))


def test_not_match():
    script = "git push -u origin master"
    assert not match(Command(script, "Everything up-to-date"))


def test_a_configuration_value_is_not_a_push():
    output = "error: src refspec master does not match any"
    assert not match(Command('git config push.default simple', output))


def test_get_new_command():
    script = "git push -u origin master"
    output = "error: src refspec master does not match any\nerror: failed to..."
    new_command = 'git commit -m "Initial commit" && git push -u origin master'
    assert get_new_command(Command(script, output)) == new_command


def test_global_options_are_preserved_for_the_initial_commit():
    script = 'git -C worktree push -u origin master'
    output = 'error: src refspec master does not match any'
    assert get_new_command(Command(script, output)) == (
        'git -C worktree commit -m "Initial commit" && '
        'git -C worktree push -u origin master')
