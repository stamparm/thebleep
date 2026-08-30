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
BSD_LS = ("ls: unrecognized option `--colr'\n"
          "usage: ls [-@ABCFGHILOPRSTUWXabcdefghiklmnopqrstuvwxy1%,] "
          "[--color=when] [-D format] [file ...]\n")
WINDOWS_GREP = ("grep: unknown option -- verbsoe\n"
                "Usage: grep [OPTION]... PATTERN [FILE]...\n"
                "Try 'grep --help' for more information.\n")
BUSYBOX_LS = ("ls: unrecognized option: colr\n"
              "BusyBox v1.37.0 (2026-01-10 15:38:28 UTC) multi-call binary.\n"
              "\n"
              "Usage: ls [-1AaCxdLHRFplinshrSXvctu] [-w WIDTH] [FILE]...\n"
              "\n"
              "List directory contents\n"
              "\n"
              "\t-1\tOne column output\n"
              "\t-a\tInclude names starting with .\n"
              "\t-A\tLike -a, but exclude . and ..\n"
              "\t-x\tList by lines\n"
              "\t-d\tList directory names, not contents\n"
              "\t-L\tFollow symlinks on command line\n"
              "\t-H\tFollow symlinks on command line\n"
              "\t-R\tRecurse\n"
              "\t-p\tAppend / to directory names\n"
              "\t-F\tAppend indicator (one of */=@|) to names\n"
              "\t-l\tLong format\n"
              "\t-i\tList inode numbers\n"
              "\t-n\tList numeric UIDs and GIDs\n"
              "\t-s\tList allocated blocks\n"
              "\t-lc\tList ctime\n"
              "\t-lu\tList atime\n"
              "\t--full-time\tList full date/time\n"
              "\t--group-directories-first\n"
              "\t--color[={always,never,auto}]\n")
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

    def test_macos_bsd_quote_style(self):
        command = Command('ls --colr', BSD_LS)
        assert match(command)
        assert get_new_command(command)[0] == 'ls --color'

    def test_windows_grep_wording(self):
        command = Command('grep --verbsoe', WINDOWS_GREP)
        assert match(command)
        assert get_new_command(command)[0] == 'grep --verbose'

    def test_busybox_wording(self):
        command = Command('ls --colr', BUSYBOX_LS)
        assert match(command)
        assert get_new_command(command)[0] == 'ls --color'

    def test_environment_assignment_is_not_used_as_the_program(self, installed):
        command = Command('LC_ALL=C ls --colour', GNU)
        assert get_new_command(command)[0] == 'LC_ALL=C ls --color'
        installed.assert_called_once_with('ls', None)

    def test_environment_assignment_preserves_git_subcommand(self, installed):
        command = Command('GIT_OPTIONAL_LOCKS=0 git status --shrot',
                          GIT_STATUS)
        assert get_new_command(command)[0] == \
            'GIT_OPTIONAL_LOCKS=0 git status --short'
        installed.assert_not_called()

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


class TestAnOptionWithAValue(object):
    """`--colour=always` -- the value is part of the argument, not of the name.

    `BROKEN` captures the option *name*, which stops at the `=`, so the value
    was silently dropped and the suggestion was a different command:

        $ diff --colour=alwys a b
        diff: unrecognized option '--colour=alwys'
        $ bleep
        diff --color a b

    Wordings captured from diffutils 3.10 and GNU coreutils 9.4.

    """

    @pytest.mark.parametrize('script, output, expected', [
        ('diff --colour=alwys a b',
         "diff: unrecognized option '--colour=alwys'\n"
         "diff: Try 'diff --help' for more information.\n",
         'diff --color=alwys a b'),
        ('ls --colr=never /tmp',
         "ls: unrecognized option '--colr=never'\n"
         "Try 'ls --help' for more information.\n",
         'ls --color=never /tmp'),
        # And without a value, which is what always worked.
        ('diff --colour a b',
         "diff: unrecognized option '--colour'\n"
         "diff: Try 'diff --help' for more information.\n",
         'diff --color a b'),
    ])
    def test_the_value_survives(self, script, output, expected):
        command = Command(script, output)
        assert match(command)
        assert get_new_command(command)[0] == expected
