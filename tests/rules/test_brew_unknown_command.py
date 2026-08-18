import pytest
from thebleep.rules.brew_unknown_command import match, get_new_command
from thebleep.rules.brew_unknown_command import _brew_commands
from thebleep.types import Command


USAGE = '''Example usage:
  brew search TEXT|/REGEX/
  brew info [FORMULA|CASK...]
  brew install FORMULA|CASK...

'''


@pytest.fixture
def brew_unknown_cmd():
    # Homebrew 4.7. The command is named after `brew ` now, and a suggestion
    # of brew's own puts `Invalid usage:` in front of the message.
    return USAGE + 'Error: Invalid usage: Unknown command: brew inst\n' \
                   'Did you mean install?\n'


@pytest.fixture
def brew_unknown_cmd2():
    return USAGE + 'Error: Invalid usage: Unknown command: brew instaa\n'


@pytest.fixture
def brew_unknown_cmd_legacy():
    return '''Error: Unknown command: inst'''


def test_match(brew_unknown_cmd, brew_unknown_cmd_legacy):
    assert match(Command('brew inst', brew_unknown_cmd))
    assert match(Command('brew inst', brew_unknown_cmd_legacy))
    for command in _brew_commands():
        assert not match(Command('brew ' + command, ''))


def test_not_match_without_a_command_name():
    """The word is there but the message is not one this rule can read."""
    assert not match(Command('brew inst', 'Unknown command\n'))


def test_get_new_command(brew_unknown_cmd, brew_unknown_cmd2):
    assert (get_new_command(Command('brew inst', brew_unknown_cmd))
            == ['brew list', 'brew install', 'brew uninstall'])

    cmds = get_new_command(Command('brew instaa', brew_unknown_cmd2))
    assert 'brew install' in cmds
    assert 'brew uninstall' in cmds
