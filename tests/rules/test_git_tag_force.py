import pytest
from thebleep.rules.git_tag_force import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def output():
    return '''fatal: tag 'alert' already exists'''


def test_match(output):
    assert match(Command('git tag alert', output))
    assert not match(Command('git tag alert', ''))


def test_a_configuration_token_is_not_a_tag():
    output = "tag.name fatal: tag 'alert' already exists"
    assert not match(Command('git config --get-regexp tag', output))


def test_get_new_command(output):
    assert (get_new_command(Command('git tag alert', output))
            == "git tag --force alert")
