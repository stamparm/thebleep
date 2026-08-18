# -*- coding: utf-8 -*-

import pytest
from thebleep.rules.git_dubious_ownership import match, get_new_command
from thebleep.types import Command


def output(directory='/srv/repo'):
    """What git says when the repository is owned by somebody else."""
    return ("fatal: detected dubious ownership in repository at '{0}'\n"
            'To add an exception for this directory, call:\n'
            '\n'
            '\tgit config --global --add safe.directory {0}\n').format(
                directory)


def older_output(directory='/srv/repo'):
    """The same refusal, worded as git 2.35 worded it."""
    return ("fatal: unsafe repository ('{0}' is owned by someone else)\n"
            'To add an exception for this directory, call:\n'
            '\n'
            '\tgit config --global --add safe.directory {0}\n').format(
                directory)


@pytest.mark.parametrize('script', ['git status', 'git add .', 'git log'])
@pytest.mark.parametrize('build_output', [output, older_output])
def test_match(script, build_output):
    assert match(Command(script, build_output()))


@pytest.mark.parametrize('script, command_output', [
    ('git status', ''),
    ('git status', 'On branch main\nnothing to commit\n'),
    # Not a git command, so not this rule's business.
    ('ls', output()),
])
def test_not_match(script, command_output):
    assert not match(Command(script, command_output))


@pytest.mark.parametrize('build_output', [output, older_output])
def test_get_new_command(build_output):
    assert get_new_command(Command('git status', build_output())) == (
        'git config --global --add safe.directory /srv/repo && git status')


def test_the_path_git_named_is_the_one_used():
    assert get_new_command(Command('git add .', output('/mnt/c/work'))) == (
        'git config --global --add safe.directory /mnt/c/work && git add .')


def test_a_path_with_a_space_is_quoted():
    """git prints the path bare, which would arrive as two arguments."""
    new_command = get_new_command(Command('git status', output('/srv/my repo')))
    assert new_command == (
        "git config --global --add safe.directory '/srv/my repo' "
        '&& git status')
