# -*- encoding: utf-8 -*-

"""`ln -s newlink existing` -> the arguments the other way round.

The rule used to move the *first* argument that exists on disk to the end. When
both exist that is the source, and the suggestion asks ln to create a link where
the source was:

    $ ln -s /etc/hostname /tmp/l1        # /tmp/l1 is already a link
    ln: failed to create symbolic link '/tmp/l1': File exists
    $ bleep
    ln -s /tmp/l1 /etc/hostname          <- a link on top of /etc/hostname

Which is destructive, for a command that was written correctly and only needed
`-f`.

"""

import pytest
from thebleep.rules.ln_s_order import match, get_new_command
from thebleep.types import Command

get_output = "ln: failed to create symbolic link '{}': File exists".format
bsd_output = 'ln: {}: File exists'.format


@pytest.fixture
def on_disk(mocker):
    """Which of these names exists, and nothing else does."""
    def _existing(*names):
        mocker.patch('os.path.exists',
                     side_effect=lambda path: path in names)

    return _existing


@pytest.mark.parametrize('script, result', [
    ('ln -s dest source', 'ln -s source dest'),
    ('ln -s dest source', 'ln -s source dest'),
    ('ln -f -s dest source', 'ln -f -s source dest'),
])
def test_the_reversed_command(on_disk, script, result):
    on_disk('source')
    command = Command(script, get_output('source'))
    assert match(command)
    assert get_new_command(command) == result


def test_environment_assignment_is_preserved(on_disk):
    on_disk('source')
    command = Command('LN_BLOCK_SIZE=1 ln -s dest source',
                      get_output('source'))
    assert match(command)
    assert get_new_command(command) == 'LN_BLOCK_SIZE=1 ln -s source dest'


def test_bsd_error(on_disk):
    on_disk('source')
    command = Command('ln -s dest source', bsd_output('source'))
    assert match(command)
    assert get_new_command(command) == 'ln -s source dest'


class TestWhenNothingNeedsReordering(object):
    def test_both_names_exist(self, on_disk):
        """The command was written correctly and wants `-f`. Swapping it puts a
        link on top of the source."""
        on_disk('/etc/hostname', '/tmp/l1')
        command = Command('ln -s /etc/hostname /tmp/l1',
                          get_output('/tmp/l1'))
        assert not match(command)

    def test_neither_exists(self, on_disk):
        on_disk()
        assert not match(Command('ln -s dest source', get_output('source')))

    def test_the_message_names_something_else(self, on_disk):
        """Then this is not the failure this rule is about."""
        on_disk('source')
        assert not match(Command('ln -s dest source',
                                 get_output('somewhere/else')))

    @pytest.mark.parametrize('script', [
        'ln dest source',                      # no -s
        'ls -s dest source',                   # not ln
        'ln -s one two three',                 # not a pair
        'ln -s dest',                          # not a pair
        'ln -s --backup=simple dest source',   # an option this cannot read
    ])
    def test_shapes_it_says_nothing_about(self, on_disk, script):
        on_disk('source')
        assert not match(Command(script, get_output('source')))

    def test_no_output_says_nothing(self, on_disk):
        on_disk('source')
        assert not match(Command('ln -s dest source', ''))

    def test_unrelated_file_exists_says_nothing(self, on_disk):
        on_disk('source')
        assert not match(Command('ln -s dest source', 'File exists'))
