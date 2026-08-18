import pytest
from thebleep.rules.cargo_no_command import match, get_new_command
from thebleep.types import Command


no_such_subcommand_old = """No such subcommand

        Did you mean `build`?
"""

no_such_subcommand = """error: no such subcommand

\tDid you mean `build`?
"""


# What cargo has said since 1.73.
no_such_command = """error: no such command: `buils`

help: a command with a similar name exists: `build`

help: view all installed commands with `cargo --list`
help: find a package to install `buils` with `cargo search cargo-buils`
"""


@pytest.mark.parametrize('command', [
    Command('cargo buid', no_such_subcommand_old),
    Command('cargo buils', no_such_subcommand),
    Command('cargo buils', no_such_command)])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    # A command cargo does not have and has nothing to suggest for.
    Command('cargo zzzz', 'error: no such command: `zzzz`\n\n'
                          'help: view all installed commands with '
                          '`cargo --list`\n'),
    Command('cargo build', ''),
    Command('vim buils', no_such_command)])
def test_not_match(command):
    assert not match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command('cargo buid', no_such_subcommand_old), 'cargo build'),
    (Command('cargo buils', no_such_subcommand), 'cargo build'),
    (Command('cargo buils', no_such_command), 'cargo build'),
    (Command('cargo buils --release', no_such_command),
     'cargo build --release')])
def test_get_new_command(command, new_command):
    assert get_new_command(command) == new_command
