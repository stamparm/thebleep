import pytest

from thebleep.rules.git_lfs_mistype import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def mistype_response():
    return """
Error: unknown command "evn" for "git-lfs"

Did you mean this?
        env
        ext

Run 'git-lfs --help' for usage.
    """


def test_match(mistype_response):
    assert match(Command('git lfs evn', mistype_response))
    err_response = 'bash: git: command not found'
    assert not match(Command('git lfs env', err_response))
    assert not match(Command('docker lfs env', mistype_response))


def test_a_word_in_an_argument_is_not_git_lfs(mistype_response):
    assert not match(Command('git config lfs.url https://example.invalid',
                             mistype_response))


def test_a_suggestion_without_the_lfs_error_is_not_a_match():
    assert not match(Command('git lfs evn', 'Did you mean this?\n        env'))


def test_get_new_command(mistype_response):
    assert (get_new_command(Command('git lfs evn', mistype_response))
            == ['git lfs env', 'git lfs ext'])
