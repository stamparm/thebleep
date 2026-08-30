import pytest
from unittest.mock import patch
from thebleep.rules import pacman_not_found
from thebleep.rules.pacman_not_found import match, get_new_command
from thebleep.types import Command

PKGFILE_OUTPUT_LLC = '''extra/llvm 3.6.0-5      /usr/bin/llc
extra/llvm35 3.5.2-13/usr/bin/llc'''


@pytest.mark.skipif(not getattr(pacman_not_found, 'enabled_by_default', True),
                    reason='Skip if pacman is not available')
@pytest.mark.parametrize('command', [
    Command('yay -S llc', 'error: target not found: llc'),
    Command('pikaur -S llc', 'error: target not found: llc'),
    Command('yaourt -S llc', 'error: target not found: llc'),
    Command('pacman llc', 'error: target not found: llc'),
    Command('sudo pacman llc', 'error: target not found: llc')])
def test_match(command):
    assert match(command)


@pytest.mark.parametrize('command', [
    Command('yay -S llc', 'error: target not found: llc'),
    Command('pikaur -S llc', 'error: target not found: llc'),
    Command('yaourt -S llc', 'error: target not found: llc'),
    Command('pacman llc', 'error: target not found: llc'),
    Command('sudo pacman llc', 'error: target not found: llc')])
@patch('thebleep.specific.archlinux.utils.tool_lines')
def test_match_mocked(tool_lines, command):
    tool_lines.return_value = PKGFILE_OUTPUT_LLC.splitlines()
    assert match(command)


@patch('thebleep.specific.archlinux.utils.tool_lines')
def test_prefixed_command_keeps_assignment(tool_lines):
    tool_lines.return_value = PKGFILE_OUTPUT_LLC.splitlines()
    command = Command('PACMAN_COLOR=0 pacman -S llc',
                      'error: target not found: llc')
    assert match(command)
    assert get_new_command(command) == [
        'PACMAN_COLOR=0 pacman -S extra/llvm',
        'PACMAN_COLOR=0 pacman -S extra/llvm35']


@pytest.mark.skipif(not getattr(pacman_not_found, 'enabled_by_default', True),
                    reason='Skip if pacman is not available')
@pytest.mark.parametrize('command, fixed', [
    (Command('yay -S llc', 'error: target not found: llc'), ['yay -S extra/llvm', 'yay -S extra/llvm35']),
    (Command('pikaur -S llc', 'error: target not found: llc'), ['pikaur -S extra/llvm', 'pikaur -S extra/llvm35']),
    (Command('yaourt -S llc', 'error: target not found: llc'), ['yaourt -S extra/llvm', 'yaourt -S extra/llvm35']),
    (Command('pacman -S llc', 'error: target not found: llc'), ['pacman -S extra/llvm', 'pacman -S extra/llvm35']),
    (Command('sudo pacman -S llc', 'error: target not found: llc'), ['sudo pacman -S extra/llvm', 'sudo pacman -S extra/llvm35'])])
def test_get_new_command(command, fixed):
    assert get_new_command(command) == fixed


@pytest.mark.parametrize('command, fixed', [
    (Command('yay -S llc', 'error: target not found: llc'), ['yay -S extra/llvm', 'yay -S extra/llvm35']),
    (Command('pikaur -S llc', 'error: target not found: llc'), ['pikaur -S extra/llvm', 'pikaur -S extra/llvm35']),
    (Command('yaourt -S llc', 'error: target not found: llc'), ['yaourt -S extra/llvm', 'yaourt -S extra/llvm35']),
    (Command('pacman -S llc', 'error: target not found: llc'), ['pacman -S extra/llvm', 'pacman -S extra/llvm35']),
    (Command('sudo pacman -S llc', 'error: target not found: llc'), ['sudo pacman -S extra/llvm', 'sudo pacman -S extra/llvm35'])])
@patch('thebleep.specific.archlinux.utils.tool_lines')
def test_get_new_command_mocked(tool_lines, command, fixed):
    tool_lines.return_value = PKGFILE_OUTPUT_LLC.splitlines()
    assert get_new_command(command) == fixed
