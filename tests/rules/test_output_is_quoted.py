# -*- coding: utf-8 -*-

"""Rules that lift a name or a path out of a command's output.

Whatever they extract ends up in a command that the shell evaluates, so it has
to arrive as one argument however it is spelled. These rules used to
interpolate it raw, which turned a path the user had quoted into code, and made
an ordinary path with a space in it fall apart into two arguments.

The check is done by running the proposed command in a real shell with the
program it calls replaced by one that reports the arguments it was handed.
Nothing less is convincing: `shlex` does not expand `$(...)` and does not treat
`;` as an operator, so it says a payload survived when a shell would have run
it.

"""

import subprocess
import sys
import pytest
from thebleep.rules import (cp_create_destination, docker_image_being_used_by_container,
                            git_add, heroku_multiple_apps, nixos_cmd_not_found,
                            no_such_file, python_module_error, touch)
from thebleep.shells import shell
from thebleep.types import Command

pytestmark = pytest.mark.skipif(sys.platform == 'win32',
                                reason='needs a POSIX shell to do the parsing')

# Each of these is a legal filename, package name or path.
HOSTILE = [
    'a;id',
    'a b',
    'a$(id)',
    'a`id`',
    "a'b",
    'a&&id',
    'a|id',
    'a>out',
    'a*',
]

# The rules that read their value out of a `'...'` delimited part of the
# output cannot be handed a value containing a quote in the first place.
NO_QUOTE = [payload for payload in HOSTILE if "'" not in payload]

# And the ones reading a whitespace-delimited word cannot be handed a space.
ONE_WORD = [payload for payload in NO_QUOTE if ' ' not in payload]


@pytest.fixture
def arguments_reaching(tmpdir):
    """Runs a proposed command and reports what its first program received."""
    bin_dir = tmpdir.mkdir('bin')
    record = tmpdir.join('argv')

    def run(new_command, program):
        if isinstance(new_command, list):
            new_command = new_command[0]

        # Only the first run is recorded: these rules propose two commands
        # joined by `&&`, and both halves are often the same program.
        probe = bin_dir.join(program)
        probe.write('#!/bin/sh\n'
                    'if [ ! -e "{0}" ]; then\n'
                    '    : > "{0}"\n'
                    '    for argument; do printf "%s\\n" "$argument" >> "{0}"; '
                    'done\n'
                    'fi\n'.format(record))
        probe.chmod(0o755)

        # `/bin/sh` by path, since PATH is cut down to the probe's directory
        # so that anything the command manages to inject fails to run.
        subprocess.call(['/bin/sh', '-c', new_command], cwd=str(tmpdir),
                        env={'PATH': str(bin_dir)},
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        assert record.check(), '{!r} never ran {}'.format(new_command, program)
        return record.read().splitlines()

    return run


@pytest.mark.parametrize('payload', NO_QUOTE)
def test_no_such_file(payload, arguments_reaching):
    output = ("mv: cannot move 'x' to '/tmp/{}/y': "
              'No such file or directory'.format(payload))
    new_command = no_such_file.get_new_command(Command('mv x y', output))
    assert arguments_reaching(new_command, 'mkdir') \
        == ['-p', '/tmp/' + payload]


@pytest.mark.parametrize('payload', NO_QUOTE)
def test_cp_create_destination(payload, arguments_reaching):
    """The destination now comes out of cp's own message rather than off the end
    of the command line, and cp wraps it in `'...'` -- so this joins the rules
    that cannot be handed a name containing a quote. What is quoted is the
    directory holding the destination, which is the part that gets made."""
    output = ("cp: cannot create regular file '{}/f.txt': "
              'No such file or directory'.format(payload))
    command = Command('cp x {}/f.txt'.format(payload), output)
    new_command = cp_create_destination.get_new_command(command)
    assert arguments_reaching(new_command, 'mkdir') == ['-p', payload]


@pytest.mark.parametrize('payload', NO_QUOTE)
def test_cp_create_destination_macos_wording_is_quoted(
        payload, arguments_reaching, tmpdir, monkeypatch):
    tmpdir.join('x').write('source\n')
    monkeypatch.chdir(str(tmpdir))
    destination = payload + '/f.txt'
    output = 'cp: {}: No such file or directory'.format(destination)
    command = Command('cp x {}'.format(shell.quote(destination)), output)
    new_command = cp_create_destination.get_new_command(command)
    assert arguments_reaching(new_command, 'mkdir') == ['-p', payload]


@pytest.mark.parametrize('payload', NO_QUOTE)
def test_touch(payload, arguments_reaching):
    output = "touch: cannot touch '/tmp/{}/f': " \
             'No such file or directory'.format(payload)
    new_command = touch.get_new_command(Command('touch f', output))
    assert arguments_reaching(new_command, 'mkdir') \
        == ['-p', '/tmp/' + payload]


@pytest.mark.parametrize('payload', HOSTILE)
def test_git_add(payload, arguments_reaching, mocker):
    mocker.patch('thebleep.rules.git_add._get_missing_file',
                 return_value=payload)
    new_command = git_add.get_new_command(Command('git add x', ''))
    assert arguments_reaching(new_command, 'git') == ['add', '--', payload]


@pytest.mark.parametrize('payload', NO_QUOTE)
def test_python_module_error(payload, arguments_reaching):
    output = "ModuleNotFoundError: No module named '{}'".format(payload)
    new_command = python_module_error.get_new_command(Command('./x.py', output))
    assert arguments_reaching(new_command, 'pip') == ['install', payload]


@pytest.mark.parametrize('payload', ONE_WORD)
def test_nixos_cmd_not_found(payload, arguments_reaching):
    output = 'nix-env -iA {}'.format(payload)
    new_command = nixos_cmd_not_found.get_new_command(Command('vim', output))
    assert arguments_reaching(new_command, 'nix-env') == ['-iA', payload]


@pytest.mark.parametrize('payload', ONE_WORD)
def test_heroku_multiple_apps(payload, arguments_reaching):
    output = 'Error: Multiple apps in git remotes\n {} (heroku)\n' \
             'https://devcenter.heroku.com/articles/multiple-environments' \
             .format(payload)
    new_command = heroku_multiple_apps.get_new_command(
        Command('heroku pg', output))
    assert arguments_reaching(new_command, 'heroku') \
        == ['pg', '--app', payload]


@pytest.mark.parametrize('payload', ONE_WORD)
def test_docker_image_being_used_by_container(payload, arguments_reaching):
    output = 'image is being used by running container {}'.format(payload)
    command = Command('docker image rm foo', output)
    new_command = docker_image_being_used_by_container.get_new_command(command)
    assert arguments_reaching(new_command, 'docker') \
        == ['container', 'rm', '-f', payload]
