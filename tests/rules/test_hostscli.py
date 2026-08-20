import pytest
from thebleep.rules.hostscli import no_website, get_new_command, match
from thebleep.types import Command

no_website_long = '''
{}:

No Domain list found for website: a_website_that_does_not_exist

Please raise a Issue here: https://github.com/dhilipsiva/hostscli/issues/new
if you think we should add domains for this website.

type `hostscli websites` to see a list of websites that you can block/unblock
'''.format(no_website)


@pytest.mark.parametrize('command', [
    Command('hostscli block a_website_that_does_not_exist', no_website_long)])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command, result', [(
    Command('hostscli block a_website_that_does_not_exist', no_website_long),
    ['hostscli websites'])])
def test_get_new_command(command, result):
    assert get_new_command(command) == result


class TestTheSubcommandHalf(object):
    """Which was dead, and had no test at all -- which is how it stayed dead.

    `re.findall(r'Error: No such command ".*"', output)[0]` has no capturing
    group, so it handed back the whole sentence rather than the name in it. That
    sentence was then looked for in the command the user typed, where it has
    never appeared, so the closeness match had nothing to work on.

    """

    # Click 8.4, which is what a current `pip install hostscli` gets.
    MODERN = ("Usage: hostscli [OPTIONS] COMMAND [ARGS]...\n"
              "Try 'hostscli --help' for help.\n\n"
              "Error: No such command 'blck'. "
              "(Did you mean one of: 'block', 'block-all', 'unblock'?)\n")

    # Older Click, which used double quotes and offered nothing.
    OLD = ('Usage: hostscli [OPTIONS] COMMAND [ARGS]...\n\n'
           'Error: No such command "blck".\n')

    def test_a_click_that_answered_for_itself_is_left_to_click(self):
        """`click_suggestion` reads that list, and it is the program's own."""
        assert not match(Command('hostscli blck', self.MODERN))

    def test_a_click_that_did_not_is_answered_here(self):
        assert match(Command('hostscli blck', self.OLD))
        assert get_new_command(Command('hostscli blck', self.OLD))[0] \
            == 'hostscli block'

    def test_the_commands_are_the_ones_hostscli_has(self):
        """They were written down as `block_all` and `unblock_all`; the program
        spells them with hyphens."""
        from thebleep.rules.hostscli import COMMANDS

        assert 'block-all' in COMMANDS
        assert 'unblock-all' in COMMANDS

    def test_a_wording_it_cannot_read_is_not_a_crash(self):
        output = 'Error: No such command and nothing quoted\n'
        assert not match(Command('hostscli blck', output))
