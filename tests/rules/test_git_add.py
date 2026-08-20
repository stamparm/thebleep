import pytest
from thebleep.rules.git_add import match, get_new_command
from thebleep.types import Command


@pytest.fixture(autouse=True)
def path_exists(mocker):
    return mocker.patch('thebleep.rules.git_add.Path.exists',
                        return_value=True)


@pytest.fixture
def output(target):
    # No full stop. git 2.43 prints `... known to git` and stops, and matching
    # the version with one had left this rule dead for however many releases
    # ago that changed -- its sibling `git_checkout`, which matches the same
    # message without it, had been answering alone.
    return ("error: pathspec '{}' did not match any "
            'file(s) known to git'.format(target))


@pytest.mark.parametrize('script, target', [
    ('git submodule update unknown', 'unknown'),
    ('git commit unknown', 'unknown')])
def test_match(output, script, target):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, target, exists', [
    ('git submodule update known', '', True),
    ('git commit known', '', True),
    ('git submodule update known', output, False)])
def test_not_match(path_exists, output, script, target, exists):
    path_exists.return_value = exists
    assert not match(Command(script, output))


@pytest.mark.parametrize('script, target, new_command', [
    ('git submodule update unknown', 'unknown',
     'git add -- unknown && git submodule update unknown'),
    ('git commit unknown', 'unknown',
     'git add -- unknown && git commit unknown')])
def test_get_new_command(output, script, target, new_command):
    assert get_new_command(Command(script, output)) == new_command


@pytest.mark.parametrize('output', [
    # git 2.43, `git checkout`/`git diff`/`git log`.
    "error: pathspec 'notes.md' did not match any file(s) known to git",
    # Older git, with the full stop this used to insist on.
    "error: pathspec 'notes.md' did not match any file(s) known to git.",
    # git 2.43, `git add -u`, `git stash push`, `git rm`.
    "fatal: pathspec 'notes.md' did not match any files",
])
def test_every_wording_git_has_used(output):
    assert match(Command('git checkout notes.md', output))
