import pytest
from thebleep.rules.git_branch_exists import match, get_new_command
from thebleep.types import Command


# git 2.38 and older: "fatal: A branch named 'x' already exists." -- capital,
# full stop. git 2.39 and newer: "fatal: a branch named 'x' already exists".
# The rule required both the capital and the stop, so it was dead on every git
# in current use while this fixture, hand-written from the old wording, stayed
# green. Captured from git 2.30.2 (old) and 2.39.5 / 2.47.3 (new).
@pytest.fixture(params=["fatal: A branch named '{}' already exists.",
                        "fatal: a branch named '{}' already exists"])
def output(request, src_branch_name):
    return request.param.format(src_branch_name)


@pytest.fixture
def new_command(branch_name, script):
    return ['git checkout {}'.format(branch_name),
            'git branch -d {} && {}'.format(branch_name, script)]


@pytest.fixture(params=["fatal: A branch named 'foo' already exists.",
                        "fatal: a branch named 'foo' already exists"])
def branch_exists_output(request):
    return request.param


@pytest.mark.parametrize('script, src_branch_name, branch_name', [
    ('git branch foo', 'foo', 'foo'),
    ('git checkout -b "let\'s-push-this"', '"let\'s-push-this"', '"let\'s-push-this"')])
def test_match(output, script, branch_name):
    assert match(Command(script, output))


@pytest.mark.parametrize('script', [
    'git branch foo',
    'git checkout -b "let\'s-push-this"'])
def test_not_match(script):
    assert not match(Command(script, ''))


@pytest.mark.parametrize('script', [
    'git checkout bar',
    'git branch -d foo',
    'git config branch.foo.remote origin',
    'git show branch foo'])
def test_an_unrelated_command_does_not_match(script, branch_exists_output):
    assert not match(Command(script, branch_exists_output))


@pytest.mark.parametrize('script', [
    'git -C worktree branch foo',
    'GIT_PAGER=cat git -C worktree checkout -b foo',
    'git switch -c foo',
    'git switch --force-create foo'])
def test_global_options_and_switch_creation_match(script, branch_exists_output):
    assert match(Command(script, branch_exists_output))


@pytest.mark.parametrize('script, src_branch_name, branch_name', [
    ('git branch foo', 'foo', 'foo'),
    # A quote in the name used to be escaped by hand as `\\'`, which escapes
    # nothing inside single quotes -- and the name was not in quotes anyway.
    ('git checkout -b "let\'s-push-this"', "let's-push-this",
     """'let'"'"'s-push-this'"""),
    # git accepts these; the shell must see them as one word.
    ('git branch f', 'feature;>PWNED', "'feature;>PWNED'"),
    ('git branch f', 'feature$(id)', "'feature$(id)'"),
    ('git branch f', 'feature&&id', "'feature&&id'")])
def test_get_new_command(output, new_command, script, src_branch_name, branch_name):
    assert get_new_command(Command(script, output)) == new_command


def test_switch_gets_switch_and_nothing_throws_away_unmerged_work():
    """`git branch -D` was the third answer, and it drops unmerged commits."""
    output = "fatal: a branch named 'feature' already exists"
    assert get_new_command(Command('git switch -c feature', output)) == [
        'git switch feature',
        'git branch -d feature && git switch -c feature']
    for script in ('git branch feature', 'git checkout -b feature origin/x'):
        assert not any('-D' in suggestion for suggestion in
                       get_new_command(Command(script, output)))
