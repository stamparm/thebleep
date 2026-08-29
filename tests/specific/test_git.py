import pytest
from thebleep.specific.git import git_subcommand_index, git_support
from thebleep.types import Command


@pytest.mark.parametrize('called, command, output', [
    ('git co', 'git checkout', "19:22:36.299340 git.c:282   trace: alias expansion: co => 'checkout'"),
    ('git com file', 'git commit --verbose file',
     "19:23:25.470911 git.c:282   trace: alias expansion: com => 'commit' '--verbose'"),
    ('git com -m "Initial commit"', 'git commit -m "Initial commit"',
     "19:22:36.299340 git.c:282   trace: alias expansion: com => 'commit'"),
    ('git br -d some_branch', 'git branch -d some_branch',
     "19:22:36.299340 git.c:282   trace: alias expansion: br => 'branch'")])
def test_git_support(called, command, output):
    @git_support
    def fn(command):
        return command.script

    assert fn(Command(called, output)) == command


@pytest.mark.parametrize('command, is_git', [
    ('git pull', True),
    ('hub pull', True),
    ('git push --set-upstream origin foo', True),
    ('hub push --set-upstream origin foo', True),
    ('ls', False),
    ('cat git', False),
    ('cat hub', False)])
@pytest.mark.parametrize('output', ['', None])
def test_git_support_match(command, is_git, output):
    @git_support
    def fn(command):
        return True

    assert fn(Command(command, output)) == is_git


def test_git_support_does_not_rewrite_an_environment_assignment():
    output = "trace: alias expansion: co => 'checkout'"

    @git_support
    def fn(command):
        return command.script

    assert fn(Command('CO=co git co', output)) == 'CO=co git checkout'


def test_git_support_ignores_an_incomplete_trace_line():
    @git_support
    def fn(command):
        return command.script

    assert fn(Command('git co', 'trace: alias expansion:')) == 'git co'


@pytest.mark.parametrize('script, expected', [
    ('git pull', 1),
    ('CO=co git -C worktree pull', 4),
    ('git -c test=test push', 3),
    ('git --git-dir repo.git commit', 3),
    ('git --git-dir=repo.git commit', 2),
    ('git config --get-regexp pull', 1),
    ('git --help pull', 3),
])
def test_git_subcommand_index(script, expected):
    assert git_subcommand_index(Command(script, '').script_parts) == expected
