import pytest
from thebleep.rules.brew_unknown_command import match, get_new_command
from thebleep.rules.brew_unknown_command import _brew_commands
from thebleep.specific import brew
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


def test_unrelated_command_is_not_a_match():
    assert not match(Command(
        'brew zzzzz', 'Error: Unknown command: zzzzz'))


class TestWhereTheCommandsAreLookedFor(object):
    """brew's own code lives under `brew --repository`, not `brew --prefix`.

    The two are the same directory on an Apple Silicon Mac and on a git-cloned
    install, and the prefix is one level above on an Intel Mac -- so a path
    built out of the prefix finds nothing on most Macs sold since 2020.

    """

    @pytest.fixture
    def repository(self, tmpdir, mocker):
        cmd = tmpdir.mkdir('Library').mkdir('Homebrew').mkdir('cmd')
        cmd.join('noodle.rb').write('')
        cmd.join('spoon.sh').write('')
        cmd.join('README.md').write('')

        tap = tmpdir.join('Library').mkdir('Taps') \
                    .mkdir('someone').mkdir('homebrew-fork').mkdir('cmd')
        tap.join('brew-fondue.rb').write('')

        mocker.patch(
            'thebleep.rules.brew_unknown_command.get_brew_repository',
            return_value=str(tmpdir))
        return tmpdir

    def test_the_commands_come_from_the_repository(self, repository):
        commands = _brew_commands()
        assert 'noodle' in commands
        assert 'spoon' in commands
        assert 'README.md' not in commands

    def test_a_tap_brings_its_own_commands(self, repository):
        assert 'fondue' in _brew_commands()


def test_the_repository_is_what_brew_is_asked_for(mocker, no_memoize):
    asked = mocker.patch('thebleep.specific.brew.tool_output',
                         return_value='/opt/homebrew\n')

    assert brew.get_brew_repository() == '/opt/homebrew'
    assert asked.call_args[0][0] == ['brew', '--repository']


def test_get_new_command(brew_unknown_cmd, brew_unknown_cmd2):
    assert (get_new_command(Command('brew inst', brew_unknown_cmd))
            == ['brew list', 'brew install', 'brew uninstall'])

    cmds = get_new_command(Command('brew instaa', brew_unknown_cmd2))
    assert 'brew install' in cmds
    assert 'brew uninstall' in cmds
