from thebleep.rules.git_clone_git_clone import match, get_new_command
from thebleep.types import Command


output_clean = """
fatal: Too many arguments.

usage: git clone [<options>] [--] <repo> [<dir>]
"""


def test_match():
    assert match(Command('git clone git clone foo', output_clean))


def test_not_match():
    assert not match(Command('', ''))
    assert not match(Command('git branch', ''))
    assert not match(Command('git clone foo', ''))
    assert not match(Command('git clone foo bar baz', output_clean))


def test_get_new_command():
    assert get_new_command(Command('git clone git clone foo', output_clean)) == 'git clone foo'


def test_get_new_command_does_not_rewrite_a_quoted_argument():
    command = Command('git clone "keep git clone here" git clone foo',
                      output_clean)

    assert get_new_command(command) == 'git clone "keep git clone here" foo'


def test_global_options_are_preserved():
    command = Command('git -C worktree clone git clone foo', output_clean)
    assert match(command)
    assert get_new_command(command) == 'git -C worktree clone foo'
