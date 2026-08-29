import pytest
from thebleep.rules.git_rm_recursive import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def output(target):
    return "fatal: not removing '{}' recursively without -r".format(target)


@pytest.mark.parametrize('script, target', [
    ('git rm foo', 'foo'),
    ('git rm foo bar', 'foo bar')])
def test_match(output, script, target):
    assert match(Command(script, output))


@pytest.mark.parametrize('script', ['git rm foo', 'git rm foo bar'])
def test_not_match(script):
    assert not match(Command(script, ''))


def test_rm_text_in_another_command_is_not_a_rm():
    output = "fatal: not removing 'foo' recursively without -r"
    assert not match(Command('git show rm foo', output))


@pytest.mark.parametrize('script, target, new_command', [
    ('git rm foo', 'foo', 'git rm -r foo'),
    ('git rm foo bar', 'foo bar', 'git rm -r foo bar')])
def test_get_new_command(output, script, target, new_command):
    assert get_new_command(Command(script, output)) == new_command


def test_get_new_command_preserves_quoted_filename():
    output = "fatal: not removing 'foo bar' recursively without -r"
    assert get_new_command(Command("git rm 'foo bar'", output)) \
        == "git rm -r 'foo bar'"
