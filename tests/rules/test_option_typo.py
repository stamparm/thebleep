# -*- encoding: utf-8 -*-

"""A mistyped long option, for any program that says so in the usual way.

Every fixture was printed by a real program: GNU coreutils 9.4, tar 1.35,
curl 8.x and git 2.47.3. Before this, the only rule that fired on any of them
was `long_form_help`, which answered `ls --help` -- and threw the rest of the
command away.

"""

import pytest
from thebleep.rules import option_typo
from thebleep.rules.option_typo import match, get_new_command
from thebleep.types import Command

# GNU: the options are not printed, only an invitation to ask.
GNU = ("ls: unrecognized option '--colour'\n"
       "Try 'ls --help' for more information.\n")
TAR = ("tar: unrecognized option '--extrat'\n"
       "Try 'tar --help' or 'tar --usage' for more information.\n")
CURL = ('curl: option --verbse: is unknown\n'
        "curl: try 'curl --help' or 'curl --manual' for more information\n")

# git prints its options, so nothing needs to be run. Note it reports the name
# without the dashes the user typed.
GIT_STATUS = (
    "error: unknown option `shrot'\n"
    'usage: git status [<options>] [--] [<pathspec>...]\n'
    '\n'
    '    -v, --[no-]verbose    be verbose\n'
    '    -s, --[no-]short      show status concisely\n'
    '    -b, --[no-]branch     show branch information\n'
)
GIT_DIFF = ('error: invalid option: --stt\n'
            'usage: git diff [<options>] [<commit>] [--] [<path>...]\n'
            '\n'
            '    --stat                show diffstat instead of patch\n')

# No invitation to ask, and no options printed: nothing to go on.
NO_HELP = 'fatal: unrecognized argument: --onelien\n'


@pytest.fixture(autouse=True)
def installed(mocker):
    """A fixed machine, so nothing here depends on the runner."""
    mocker.patch.object(option_typo, 'which',
                        side_effect=lambda name: '/usr/bin/' + name)
    return mocker.patch.object(
        option_typo, '_options_from_help',
        return_value=['color', 'column', 'all', 'almost-all', 'extract',
                      'exclude', 'verbose', 'version', 'reverse'])


class TestReadingTheOutput(object):
    def test_git_prints_its_options_so_nothing_is_run(self, installed):
        assert get_new_command(
            Command('git status --shrot', GIT_STATUS))[0] == \
            'git status --short'
        assert not installed.called, 'the answer was in the output'

    def test_a_negatable_option_gives_its_plain_name(self):
        """git writes `--[no-]short`, and `--short` is what was meant."""
        assert '--[no-]' not in get_new_command(
            Command('git status --shrot', GIT_STATUS))[0]

    def test_another_of_gits_wordings(self):
        assert get_new_command(
            Command('git diff --stt', GIT_DIFF))[0] == 'git diff --stat'


class TestAskingTheProgram(object):
    @pytest.mark.parametrize('script, output, expected', [
        ('ls --colour', GNU, 'ls --color'),
        ('tar --extrat -f x.tar', TAR, 'tar --extract -f x.tar'),
        ('curl --verbse http://x', CURL, 'curl --verbose http://x'),
    ])
    def test_when_the_program_invited_it(self, script, output, expected):
        assert get_new_command(Command(script, output))[0] == expected

    def test_help_is_not_a_candidate(self, installed):
        """`Try 'ls --help'` puts `--help` in the output, and reading that as a
        candidate is what made `--colour` answer `--help` at first."""
        assert '--help' not in get_new_command(Command('ls --colour', GNU))[0]

    def test_nothing_is_run_without_an_invitation(self, installed):
        assert get_new_command(Command('git log --onelien', NO_HELP)) == []
        assert not installed.called


class TestNotMatching(object):
    @pytest.mark.parametrize('script, output', [
        ('ls -l', ''),
        # The option named is not in the command, so there is nothing to
        # replace -- somebody else's output.
        ('ls -l', "ls: unrecognized option '--colour'\n"),
    ])
    def test_it_says_nothing(self, script, output):
        assert not match(Command(script, output))

    def test_an_unknown_program_is_not_run(self, mocker):
        mocker.patch.object(option_typo, 'which', return_value=None)
        assert not match(Command('nosuchprog --colour', GNU))


def test_nothing_close_enough_is_no_answer(installed):
    """`ls --zzzzzzqqq` is not a typo of anything, and a help screen dressed as
    a correction is what this rule exists to replace."""
    installed.return_value = ['color', 'all']
    assert get_new_command(
        Command('ls --zzzzzzqqq',
                "ls: unrecognized option '--zzzzzzqqq'\n"
                "Try 'ls --help' for more information.\n")) == []
