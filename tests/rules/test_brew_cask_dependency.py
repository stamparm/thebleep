import pytest
from thebleep.rules.brew_cask_dependency import match, get_new_command
from thebleep.types import Command


# Homebrew 4.7, whose Requirement#message names the cask with a flag.
output = '''sshfs: OsxfuseRequirement unsatisfied!
You can install the necessary cask with:
  brew install --cask osxfuse

You can download from:
  https://osxfuse.github.io/
Error: An unsatisfied requirement failed this build.'''

# The same thing when brew still had a `cask` command of its own.
legacy_output = '''sshfs: OsxfuseRequirement unsatisfied!

You can install with Homebrew-Cask:
  brew cask install osxfuse

You can download from:
  https://osxfuse.github.io/
Error: An unsatisfied requirement failed this build.'''


@pytest.mark.parametrize('command_output', [output, legacy_output])
def test_match(command_output):
    command = Command('brew install sshfs', command_output)
    assert match(command)


@pytest.mark.parametrize('script, output', [
    ('brew link sshfs', output),
    ('cat output', output),
    ('brew install sshfs', '')])
def test_not_match(script, output):
    command = Command(script, output)
    assert not match(command)


@pytest.mark.parametrize('before, command_output, after', [
    ('brew install sshfs', output,
     'brew install --cask osxfuse && brew install sshfs'),
    ('brew install sshfs', legacy_output,
     'brew cask install osxfuse && brew install sshfs')])
def test_get_new_command(before, command_output, after):
    command = Command(before, command_output)
    assert get_new_command(command) == after


def test_get_new_command_quotes_output_words():
    hostile = output.replace('osxfuse', 'a;touch')

    command = Command('brew install sshfs', hostile)

    assert get_new_command(command) == (
        "brew install --cask 'a;touch' && brew install sshfs")


def test_several_casks_are_each_quoted_then_chained():
    """Quoting the joined chain made `&&` a word for brew to install."""
    from thebleep.shells import shell

    output = ('Error: sshfs: Cask dependencies:\n'
              '  brew install --cask osxfuse\n'
              '  brew install --cask foo\n')
    got = get_new_command(Command('brew install sshfs', output))
    assert got == shell.and_('brew install --cask osxfuse',
                             'brew install --cask foo', 'brew install sshfs')


def test_a_mention_without_a_line_of_its_own_is_left_alone():
    output = 'run `brew install --cask osxfuse` first'
    assert not match(Command('brew install sshfs', output))
