import pytest
from thebleep.rules.git_two_dashes import match, get_new_command
from thebleep.types import Command


# What real gits print. 2.30.2, 2.39.5 and 2.47.3 all say `(with two dashes)?`
# -- the question mark outside the bracket. The rule wanted `(with two dashes ?)`
# and so had never matched any of them, while this fixture, written by hand from
# the old wording, kept the test green. The old form is kept as a second case
# rather than replaced.
def output(flag):
    return 'error: did you mean `{}` (with two dashes)?'.format(flag)


def output_old(flag):
    return 'error: did you mean `{}` (with two dashes ?)'.format(flag)


@pytest.mark.parametrize('command', [
    Command('git add -patch', output('--patch')),
    Command('git checkout -patch', output('--patch')),
    Command('git commit -amend', output('--amend')),
    Command('git push -tags', output('--tags')),
    Command('git rebase -continue', output('--continue')),
    Command('git add -patch', output_old('--patch')),
    Command('git commit -amend', output_old('--amend'))])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('git add --patch', ''),
    Command('git checkout --patch', ''),
    Command('git commit --amend', ''),
    Command('git push --tags', ''),
    Command('git rebase --continue', '')])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, output', [
    (Command('git add -patch', output('--patch')),
        'git add --patch'),
    (Command('git checkout -patch', output('--patch')),
        'git checkout --patch'),
    (Command('git checkout -patch', output('--patch')),
        'git checkout --patch'),
    (Command('git init -bare', output('--bare')),
        'git init --bare'),
    (Command('git commit -amend', output('--amend')),
        'git commit --amend'),
    (Command('git push -tags', output('--tags')),
        'git push --tags'),
    (Command('git rebase -continue', output('--continue')),
        'git rebase --continue')])
def test_get_new_command(command, output):
    assert get_new_command(command) == output
