# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules.unknown_subcommand import get_new_command, match
from thebleep.types import Command

# Printed by Go 1.22.12, Docker 20.10.17, cargo 1.98.0 and git 2.43.0.
GO = "go biuld: unknown command\nRun 'go help' for usage.\n"
DOCKER = "docker: 'pss' is not a docker command.\nSee 'docker --help'\n"
CARGO = ('error: no such command: `biuld`\n\n'
         'help: view all installed commands with `cargo --list`\n'
         'help: find a package to install `biuld` with `cargo search '
         'cargo-biuld`\n')
GIT_FAR = "git: 'zzzqqq' is not a git command. See 'git --help'.\n"
BREW = 'Error: Unknown command: isntall\n'

# Outputs that name the answer belong to the rules that read them.
GIT_NAMED = ("git: 'sttus' is not a git command. See 'git --help'.\n\n"
             'The most similar command is\n\tstatus\n')
COBRA = ('Error: unknown command "gt" for "kubectl"\n\nDid you mean this?\n'
         '\tget\n')


@pytest.fixture(autouse=True)
def installed(mocker):
    mocker.patch('thebleep.rules.unknown_subcommand.which',
                 side_effect=lambda name: '/usr/bin/' + name)


@pytest.fixture
def manual(mocker):
    known = {
        ('go', ()): ['build', 'bug', 'clean', 'doc', 'env', 'fix', 'fmt',
                     'generate', 'get', 'install', 'list', 'mod', 'run',
                     'test', 'tool', 'version', 'vet'],
        ('docker', ()): ['attach', 'build', 'commit', 'cp', 'create', 'diff',
                         'events', 'exec', 'export', 'history', 'image',
                         'images', 'import', 'info', 'inspect', 'kill', 'load',
                         'login', 'logout', 'logs', 'pause', 'port', 'ps',
                         'pull', 'push'],
        ('docker', ('image',)): ['build', 'history', 'import', 'inspect',
                                 'load', 'ls', 'prune', 'pull', 'push', 'rm',
                                 'save', 'tag'],
        ('cargo', ()): ['add', 'bench', 'build', 'check', 'clean', 'doc'],
        ('git', ()): ['add', 'status', 'commit'],
        ('brew', ()): ['install', 'uninstall', 'info'],
    }
    return mocker.patch('thebleep.vocabulary.subcommands',
                        side_effect=lambda tool, prefix=():
                        list(known.get((tool, tuple(prefix)), [])))


@pytest.mark.parametrize('script, output', [
    ('go biuld ./...', GO), ('docker pss', DOCKER), ('cargo biuld', CARGO),
    ('git zzzqqq', GIT_FAR), ('brew isntall vim', BREW)])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('git sttus', GIT_NAMED), ('kubectl gt pods', COBRA),
    ('go', GO), ('ls', 'ls: cannot access x'),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


@pytest.mark.usefixtures('manual')
class TestFromTheManual(object):
    def test_go(self):
        assert get_new_command(Command('go biuld ./...', GO)) == [
            'go build ./...']

    def test_docker(self):
        assert get_new_command(Command('docker pss', DOCKER)) == ['docker ps']

    def test_a_command_under_a_command(self):
        output = "docker: 'lss' is not a docker command.\nSee 'docker --help'\n"
        assert get_new_command(Command('docker image lss', output)) == [
            'docker image ls']

    def test_cargo(self):
        assert get_new_command(Command('cargo biuld', CARGO)) == ['cargo build']

    def test_brew(self):
        assert get_new_command(Command('brew isntall vim', BREW)) == [
            'brew install vim']

    def test_nothing_close_is_nothing(self):
        assert get_new_command(Command('git zzzqqq', GIT_FAR)) == []

    def test_options_before_the_word_are_not_a_prefix(self):
        assert get_new_command(Command('go -x biuld', GO)) == ['go -x build']

    def test_the_broken_word_has_to_have_been_typed(self):
        assert get_new_command(Command('go build', GO)) == []


def test_no_manual_no_answer(mocker):
    mocker.patch('thebleep.vocabulary.subcommands', return_value=[])
    assert get_new_command(Command('go biuld', GO)) == []


def test_the_program_has_to_exist(mocker, manual):
    mocker.patch('thebleep.rules.unknown_subcommand.which', return_value=None)
    assert get_new_command(Command('go biuld', GO)) == []


def test_candidates_are_quoted(mocker):
    mocker.patch('thebleep.vocabulary.subcommands',
                 return_value=['bui$(touch x)ld'])
    assert get_new_command(Command('go build', GO.replace('biuld', 'build'))) \
        == []
    assert get_new_command(Command('go buld', GO.replace('biuld', 'buld'))) \
        == []
