# -*- encoding: utf-8 -*-

"""`git diff` that showed nothing, and `git diff` that failed.

The rule used to be `'diff' in command.script and '--staged' not in
command.script`, so it fired on a failing `git diff` too and added `--staged`
in front of an error it did nothing about:

    $ git diff README.md --cached
    fatal: option '--cached' must come before non-option arguments
    $ bleep
    git diff --staged README.md --cached

which fails in exactly the same way.

"""

import pytest
from thebleep.rules.git_diff_staged import match, get_new_command
from thebleep.types import Command


@pytest.fixture
def exited(os_environ):
    from thebleep import replay

    def _with(status):
        if status is None:
            os_environ.pop(replay.EXIT_ENV, None)
        else:
            os_environ[replay.EXIT_ENV] = str(status)

    return _with


class TestAfterADiffThatWorked(object):
    @pytest.mark.parametrize('script, expected', [
        ('git diff', 'git diff --staged'),
        ('git diff foo', 'git diff --staged foo'),
    ])
    def test_it_offers_the_staged_one(self, exited, script, expected):
        exited(0)
        command = Command(script, '')
        assert match(command)
        assert get_new_command(command) == expected


class TestWhenItShouldStandAside(object):
    def test_a_configuration_token_is_not_a_diff(self, exited):
        exited(0)
        assert not match(Command('git config --get-regexp diff', ''))

    def test_a_diff_that_failed(self, exited):
        """`git_flag_after_filename` knows this message and gets it right."""
        exited(1)
        output = ("fatal: option '--cached' must come before non-option "
                  'arguments\n')
        assert not match(Command('git diff README.md --cached', output))

    @pytest.mark.parametrize('script', [
        'git diff --staged', 'git diff --staged foo', 'git diff --cached',
    ])
    def test_already_asking_for_it(self, exited, script):
        exited(0)
        assert not match(Command(script, ''))

    def test_when_the_shell_did_not_say(self, exited):
        exited(None)
        assert not match(Command('git diff', ''))

    def test_a_different_subcommand(self, exited):
        exited(0)
        assert not match(Command('git status', ''))
        # `diff` as a filename rather than the subcommand.
        assert not match(Command('git add diff.txt', ''))
