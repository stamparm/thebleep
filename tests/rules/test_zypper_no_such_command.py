# -*- encoding: utf-8 -*-

"""What zypper actually prints, taken from a real one.

Every string here was captured from `opensuse/tumbleweed`, zypper 1.14.98 --
which is the point. A rule that looks for a message somebody remembered stops
working the day the tool rewords it, and half of what needed fixing in the rules
inherited from The Fuck was exactly that.

"""

import pytest
from thebleep.rules.zypper_no_such_command import (
    _parse_operations, get_new_command, match)
from thebleep.types import Command

# `zypper isntall vim`, verbatim.
UNKNOWN = u"""Unknown command 'isntall'
Type 'zypper help' to get a list of global options and commands.

In case 'isntall' is not a typo it's probably not a built-in command, but \
provided as a subcommand or plug-in (see 'zypper help subcommand').
In this case a specific package providing the subcommand needs to be installed \
first. Those packages are often named 'zypper-isntall' or \
'zypper-isntall-plugin'.
"""

# `zypper --help`, abridged to the shapes that matter: a command with one
# abbreviation, one with two, one with none, one whose name wraps onto the next
# line, and a description that wraps -- whose continuation must not be read as a
# command called `by`.
HELP = u"""Usage:

    zypper [--GLOBAL-OPTIONS] <COMMAND> [--COMMAND-OPTIONS] [ARGUMENTS]

Global Options:

    --help, -h              Help. Default: false
    --non-interactive, -n   Do not ask anything, use default answers.

Commands:

      help, ?               Print zypper help

  Repository Management:

      refresh, ref          Refresh all repositories.
      refresh-services, refs
                            Refresh all services.

  Software Management:

      install, in           Install packages.
      remove, rm            Remove packages.

  Querying:

      info, if, show        Show full information for specified packages.

  Other Commands:

      patch                 Install needed patches.
      ps                    List running processes which might still use files \
and libraries deleted
                            by recent upgrades.
"""


class TestReadingTheCommands(object):
    def test_a_command_and_its_abbreviation(self):
        found = _parse_operations(HELP)
        assert 'install' in found and 'in' in found

    def test_two_abbreviations(self):
        assert set(['info', 'if', 'show']) <= set(_parse_operations(HELP))

    def test_a_command_with_no_abbreviation(self):
        assert 'patch' in _parse_operations(HELP)

    def test_a_name_that_wrapped_onto_the_next_line(self):
        found = _parse_operations(HELP)
        assert 'refresh-services' in found and 'refs' in found

    def test_a_wrapped_description_is_not_read_as_a_command(self):
        """`by recent upgrades.` is indented differently, and is not a
        command."""
        assert 'by' not in _parse_operations(HELP)

    def test_the_global_options_are_not_commands(self):
        assert not [name for name in _parse_operations(HELP)
                    if name.startswith('-')]

    def test_the_section_headings_are_not_commands(self):
        found = _parse_operations(HELP)
        assert 'Querying' not in found
        assert 'Software' not in found

    def test_nothing_useful_out_of_nothing(self):
        """`zypper` missing, or refusing to say: no candidates, no crash."""
        assert _parse_operations(u'') == []


class TestMatching(object):
    def test_an_unknown_command(self):
        assert match(Command('zypper isntall vim', UNKNOWN))

    def test_behind_sudo(self):
        assert match(Command('sudo zypper isntall vim', UNKNOWN))

    @pytest.mark.parametrize('script, output', [
        # Right command, and something else went wrong.
        ('zypper install nosuchpackage',
         u"'nosuchpackage' not found in package names. Trying capabilities.\n"
         u"No provider of 'nosuchpackage' found."),
        ('zypper install vim',
         u'Root privileges are required to run this command.'),
        ('zypper --nosuchopt install vim',
         u'The flag --nosuchopt is not known.'),
        # Somebody else's unknown command.
        ('dnf isntall vim', u'No such command: isntall.'),
        ('zypper install vim', u''),
    ])
    def test_not_matching(self, script, output):
        assert not match(Command(script, output))


class TestCorrecting(object):
    @pytest.fixture(autouse=True)
    def operations(self, mocker):
        mocker.patch(
            'thebleep.rules.zypper_no_such_command._get_operations',
            return_value=_parse_operations(HELP))

    def test_the_close_command(self):
        assert 'zypper install vim' in get_new_command(
            Command('zypper isntall vim', UNKNOWN))

    def test_an_abbreviation_is_a_candidate_too(self):
        """`in`, `ref`, `rm` are what half of zypper's users type."""
        output = UNKNOWN.replace('isntall', 'ifno')
        assert 'zypper info' in get_new_command(
            Command('zypper ifno vim', output))[0]

    def test_the_wrapper_comes_back_in_front(self):
        assert 'sudo zypper install vim' in get_new_command(
            Command('sudo zypper isntall vim', UNKNOWN))

    def test_a_message_it_cannot_read_the_name_out_of(self):
        """`match` is case-insensitive and this is not; nothing to raise
        about."""
        assert get_new_command(
            Command('zypper isntall vim', u'unknown command: isntall')) == []
