import pytest
from thebleep.rules.git_rebase_merge_dir import match, get_new_command
from thebleep.types import Command


# Captured from git 2.43, verbatim -- including the blank line on the end.
#
# The fixture used to have two blank lines at the *start* and one newline at the
# end, which is not what git prints, and it was the shape that made
# `split("\n")[-4]` land on the `rm` line. Against the real message that index
# is a sentence of prose two lines above it, so the rule offered prose as a
# command and never offered the `rm`.
REAL = ('fatal: It seems that there is already a rebase-merge directory, and\n'
        'I wonder if you are in the middle of another rebase.  If that is the\n'
        'case, please try\n'
        '\tgit rebase (--continue | --abort | --skip)\n'
        'If that is not the case, please\n'
        '\trm -fr "/foo/bar/baz/egg/.git/rebase-merge"\n'
        'and run me again.  I am stopping in case you still have something\n'
        'valuable there.\n\n')


@pytest.fixture
def output():
    return REAL


@pytest.mark.parametrize('script', [
    'git rebase master',
    'git rebase -skip',
    'git rebase'])
def test_match(output, script):
    assert match(Command(script, output))


@pytest.mark.parametrize('script', ['git rebase master', 'git rebase -abort'])
def test_not_match(script):
    assert not match(Command(script, ''))


@pytest.mark.parametrize('script, result', [
    ('git rebase master', [
        'git rebase --abort', 'git rebase --skip', 'git rebase --continue',
        'rm -fr "/foo/bar/baz/egg/.git/rebase-merge"']),
    ('git rebase -skip', [
        'git rebase --skip', 'git rebase --abort', 'git rebase --continue',
        'rm -fr "/foo/bar/baz/egg/.git/rebase-merge"']),
    ('git rebase', [
        'git rebase --skip', 'git rebase --abort', 'git rebase --continue',
        'rm -fr "/foo/bar/baz/egg/.git/rebase-merge"'])])
def test_get_new_command(output, script, result):
    assert get_new_command(Command(script, output)) == result


@pytest.mark.parametrize('output', [
    REAL,
    REAL.strip(),
    REAL.replace('\n', '\r\n'),
])
def test_the_rm_is_offered_whatever_the_reader_did_to_the_output(output):
    """One reader strips what it hands over and one does not, so counting lines
    from either end is counting something that moves."""
    assert 'rm -fr "/foo/bar/baz/egg/.git/rebase-merge"' in \
        get_new_command(Command('git rebase master', output))


def test_no_rm_line_is_not_a_crash():
    """A wording that moves far enough to lose it still leaves three real
    answers."""
    output = ('It seems that there is already a rebase-merge directory, and\n'
              'I wonder if you are in the middle of another rebase.\n')
    assert sorted(get_new_command(Command('git rebase master', output))) == [
        'git rebase --abort', 'git rebase --continue', 'git rebase --skip']
