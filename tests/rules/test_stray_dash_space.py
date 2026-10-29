# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.stray_dash_space import get_new_command, match
from thebleep.types import Command


# What the tools printed, coreutils 9 and git 2.43, LC_ALL=C.
@pytest.mark.parametrize('script, output, fixed', [
    ('ls - la', "ls: cannot access '-': No such file or directory\n"
                "ls: cannot access 'la': No such file or directory\n",
     'ls -la'),
    ('git log - p', "fatal: ambiguous argument 'p': unknown revision or path"
                    " not in the working tree.\n", 'git log -p'),
    ('git commit - m x', "error: pathspec '-' did not match any file(s) "
                         "known to git\n", 'git commit -m x'),
    ('grep - r foo .', 'grep: r: No such file or directory\n'
                       'grep: .: Is a directory\n', 'grep -r foo .'),
    ('head - n 3 f', "head: cannot open 'n' for reading: No such file or "
                     "directory\n", 'head -n 3 f'),
    ('uname - a', "uname: extra operand '-'\n", 'uname -a'),
    ('du - sh - x .', "du: cannot access '-': No such file or directory\n",
     'du -sh -x .'),
])
def test_the_dash_and_its_letters_are_joined(script, output, fixed):
    command = Command(script, output)
    assert match(command)
    assert get_new_command(command) == fixed


@pytest.mark.parametrize('script, output', [
    ('cat - f', 'hi\n'),                       # stdin, and it worked
    ('cd -', ''),
    ('git checkout -', "error: pathspec '-' did not match any file(s) "
                       "known to git\n"),     # nothing after the dash
    ('ls - la', ''),                           # no complaint, no evidence
    ('ls - longword', "ls: cannot access '-': No such file or directory\n"),
    ('git commit -m "a - b"', "error: pathspec 'b' did not match\n"),
])
def test_a_dash_that_is_an_argument_is_left_alone(script, output):
    assert not match(Command(script, output))
