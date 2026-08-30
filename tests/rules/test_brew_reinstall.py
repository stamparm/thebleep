import pytest
from thebleep.types import Command
from thebleep.rules.brew_reinstall import get_new_command, match


# Homebrew 4.7.
output = ("Warning: thebleep 9.9 is already installed and up-to-date.\n"
          "To reinstall 9.9, run:\n"
          "  brew reinstall thebleep\n")

# The same thing before brew moved the command onto its own line.
legacy_output = ("Warning: thebleep 9.9 is already installed and up-to-date\n"
                 "To reinstall 9.9, run `brew reinstall thebleep`")


@pytest.mark.parametrize('command_output', [output, legacy_output])
def test_match(command_output):
    command = Command('brew install thebleep', command_output)
    assert match(command)


@pytest.mark.parametrize('script', [
    'brew reinstall thebleep',
    'brew install foo'])
def test_not_match(script):
    assert not match(Command(script, ''))


def test_reinstall_is_not_an_install_command():
    assert not match(Command('brew reinstall thebleep', output))


@pytest.mark.parametrize('script, formula, ', [
    ('brew install foo', 'foo'),
    ('brew install bar zap', 'bar zap')])
def test_get_new_command(script, formula):
    command = Command(script, output)
    new_command = 'brew reinstall {}'.format(formula)
    assert get_new_command(command) == new_command
