# -*- encoding: utf-8 -*-

"""`ls --sort=nmae` -> `ls --sort=name`, from the list the tool printed.

Every one of these is captured from GNU coreutils 9.4. The message belongs to
gnulib's `argmatch`, which is why it is not an `ls` feature: `du --time`,
`ls --format` and `df --output` print exactly the same shape.

What The Bleep used to answer was `ls --help` -- `long_form_help` matching the
last line of it, throwing the rest of the command away and offering a help
screen as a correction.

"""

import pytest
from thebleep.rules.invalid_argument_for_option import match, get_new_command
from thebleep.types import Command

LS_SORT = ("ls: invalid argument 'nmae' for '--sort'\n"
           'Valid arguments are:\n'
           "  - 'none'\n"
           "  - 'time'\n"
           "  - 'size'\n"
           "  - 'extension'\n"
           "  - 'version'\n"
           "  - 'width'\n"
           "Try 'ls --help' for more information.\n")

DU_TIME = ("du: invalid argument 'atme' for '--time'\n"
           'Valid arguments are:\n'
           "  - 'atime', 'access', 'use'\n"
           "  - 'ctime', 'status'\n"
           "Try 'du --help' for more information.\n")

# The same message in a UTF-8 locale, where gnulib uses typographic quotes, and
# `ambiguous` rather than `invalid` for a prefix that matches several values.
LS_QUOTING = (u"ls: ambiguous argument ‘shel’ for"
              u" ‘--quoting-style’\n"
              u'Valid arguments are:\n'
              u"  - ‘literal’\n"
              u"  - ‘shell’\n"
              u"  - ‘shell-always’\n"
              u"Try 'ls --help' for more information.\n")


@pytest.mark.parametrize('script, output, first', [
    ('ls -l --sort=nmae', LS_SORT, 'ls -l --sort=none'),
    ('du --time=atme x', DU_TIME, 'du --time=atime x'),
    (u'ls --quoting-style=shel', LS_QUOTING, 'ls --quoting-style=shell'),
    # The value as a separate word, which is the other way of writing it.
    ('ls --sort nmae', LS_SORT, 'ls --sort none'),
])
def test_it_offers_what_the_tool_listed(script, output, first):
    command = Command(script, output)
    assert match(command)
    assert get_new_command(command)[0] == first


def test_every_value_is_offered_and_only_those(script=None):
    command = Command('ls --sort=nmae', LS_SORT)
    offered = get_new_command(command)
    assert len(offered) == 3, 'three suggestions, best first'
    for suggestion in offered:
        assert suggestion.startswith('ls --sort=')
        assert suggestion.split('=')[1] in (
            'none', 'time', 'size', 'extension', 'version', 'width')


def test_the_rest_of_the_command_survives():
    """Which is the whole complaint against the answer this replaced."""
    command = Command('ls -l -h --sort=nmae /tmp', LS_SORT)
    assert get_new_command(command)[0] == 'ls -l -h --sort=none /tmp'


class TestWhenItSaysNothing(object):
    @pytest.mark.parametrize('output', [
        '',
        # The rejection without the listing: nothing to offer.
        "ls: invalid argument 'nmae' for '--sort'\n"
        "Try 'ls --help' for more information.\n",
        # A listing with nothing in it.
        "ls: invalid argument 'nmae' for '--sort'\nValid arguments are:\n"
        "Try 'ls --help'.\n",
        # Somebody else's error entirely.
        "sort: unrecognized option '--sort-key=x'\n"
        "Try 'sort --help' for more information.\n",
    ])
    def test_output_it_cannot_read(self, output):
        assert not match(Command('ls --sort=nmae', output))


def test_a_value_that_needs_quoting_gets_it():
    """These come out of the program's own output, and the result is handed to
    the shell to be evaluated."""
    output = ("prog: invalid argument 'x' for '--mode'\n"
              'Valid arguments are:\n'
              "  - 'a b; rm -rf ~'\n"
              "Try 'prog --help'.\n")
    assert get_new_command(Command('prog --mode=x', output))[0] \
        == "prog --mode='a b; rm -rf ~'"


def test_it_comes_before_the_help_screen():
    """`long_form_help` matches the last line of this output and answers
    `ls --help`, with the rest of the command discarded."""
    from thebleep.rules import invalid_argument_for_option, long_form_help

    assert invalid_argument_for_option.priority < long_form_help.priority
