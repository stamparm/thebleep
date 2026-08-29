import pytest
from thebleep.rules.git_rm_staged import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def output(target):
    return ('error: the following file has changes staged in the index:\n    {}\n(use '
            '--cached to keep the file, or -f to force removal)').format(target)


@pytest.mark.parametrize('script, target', [
    ('git rm foo', 'foo'),
    ('git rm foo bar', 'bar')])
def test_match(output, script, target):
    assert match(Command(script, output))


@pytest.mark.parametrize('script', ['git rm foo', 'git rm foo bar', 'git rm'])
def test_not_match(script):
    assert not match(Command(script, ''))


def test_rm_text_in_another_command_is_not_a_rm():
    output = ('error: the following file has changes staged in the index: foo\n'
              '(use --cached to keep the file, or -f to force removal)')
    assert not match(Command('git show rm foo', output))


@pytest.mark.parametrize('script, target, new_command', [
    ('git rm foo', 'foo', ['git rm --cached foo', 'git rm -f foo']),
    ('git rm foo bar', 'bar', ['git rm --cached foo bar', 'git rm -f foo bar'])])
def test_get_new_command(output, script, target, new_command):
    assert get_new_command(Command(script, output)) == new_command


def test_get_new_command_preserves_quoted_filename():
    output = ('error: the following file has changes staged in the index: '
              'foo bar\n(use --cached to keep the file, or -f to force removal)')
    command = Command("git rm 'foo bar'", output)
    assert get_new_command(command) == [
        "git rm --cached 'foo bar'", "git rm -f 'foo bar'"]
