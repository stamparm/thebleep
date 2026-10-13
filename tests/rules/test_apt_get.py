import pytest
from thebleep.rules.apt_get import match, get_new_command
from thebleep.types import Command


@pytest.mark.parametrize('command, packages', [
    (Command('vim', 'vim: command not found'),
     [('vim', 'main'), ('vim-tiny', 'main')]),
    (Command('sudo vim', 'vim: command not found'),
     [('vim', 'main'), ('vim-tiny', 'main')]),
    (Command('vim', "The program 'vim' is currently not installed. You can install it by typing: sudo apt install vim"),
     [('vim', 'main'), ('vim-tiny', 'main')])])
def test_match(mocker, command, packages):
    mocker.patch('thebleep.rules.apt_get.which', return_value=None)
    mocker.patch('thebleep.rules.apt_get._get_packages',
                 create=True, return_value=packages)

    assert match(command)


@pytest.mark.parametrize('command, packages, which', [
    (Command('a_bad_cmd', 'a_bad_cmd: command not found'),
     [], None),
    (Command('vim', ''), [], None),
    (Command('', ''), [], None),
    (Command('vim', 'vim: command not found'),
     ['vim'], '/usr/bin/vim'),
    (Command('sudo vim', 'vim: command not found'),
     ['vim'], '/usr/bin/vim')])
def test_not_match(mocker, command, packages, which):
    mocker.patch('thebleep.rules.apt_get.which', return_value=which)
    mocker.patch('thebleep.rules.apt_get._get_packages',
                 create=True, return_value=packages)

    assert not match(command)


@pytest.mark.parametrize('command, new_command, packages', [
    (Command('vim', ''), 'sudo apt-get install vim && vim',
     [('vim', 'main'), ('vim-tiny', 'main')]),
    (Command('convert', ''), 'sudo apt-get install imagemagick && convert',
     [('imagemagick', 'main'),
      ('graphicsmagick-imagemagick-compat', 'universe')]),
    (Command('sudo vim', ''), 'sudo apt-get install vim && sudo vim',
     [('vim', 'main'), ('vim-tiny', 'main')]),
    (Command('sudo convert', ''), 'sudo apt-get install imagemagick && sudo convert',
     [('imagemagick', 'main'),
      ('graphicsmagick-imagemagick-compat', 'universe')])])
def test_get_new_command(mocker, command, new_command, packages):
    mocker.patch('thebleep.rules.apt_get._get_packages',
                 create=True, return_value=packages)

    assert get_new_command(command) == new_command


def test_what_command_not_found_printed_is_enough(mocker):
    """ubuntu:24.04: the CommandNotFound module cannot be imported from a pipx
    or uv environment, and the shell had already said what to install."""
    mocker.patch('thebleep.rules.apt_get.which', return_value=None)
    mocker.patch('thebleep.rules.apt_get._get_packages', None)
    output = ("Command 'fortune' not found, but can be installed with:\n"
              "sudo apt install fortune-mod\n")
    command = Command('fortune', output)
    assert match(command)
    assert get_new_command(command) == \
        'sudo apt-get install fortune-mod && fortune'
    assert not match(Command('fortune', "Command 'other' not found, but can "
                             "be installed with:\napt install x\n"))
