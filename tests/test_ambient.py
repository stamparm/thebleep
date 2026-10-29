# -*- encoding: utf-8 -*-

"""`git satus` -> `git status` before anything runs: `thebleep.ambient`."""

import os

import pytest

from thebleep import ambient

GIT = ['add', 'branch', 'checkout', 'citool', 'commit', 'config', 'diff',
       'diff-files', 'difftool', 'log', 'status', 'stash']


@pytest.fixture
def vocabulary(mocker):
    """git documents `GIT`; docker documents `ps` and `pull`; `ls`, `cat`
    and `ssh` document no subcommands at all."""
    known = {'git': GIT, 'docker': ['ps', 'pull', 'run'],
             'npm': ['install', 'init', 'test']}
    return mocker.patch('thebleep.vocabulary.subcommands',
                        side_effect=lambda tool, prefix=(): list(
                            known.get(tool, [])))


@pytest.fixture
def path(mocker, tmp_path, monkeypatch):
    """A PATH with `git-lg` on it and nothing else."""
    (tmp_path / 'bin').mkdir()
    plugin = tmp_path / 'bin' / 'git-lg'
    plugin.write_text('#!/bin/sh\n')
    plugin.chmod(0o755)
    mocker.patch('thebleep.ambient.which',
                 side_effect=lambda name: str(plugin) if name == 'git-lg'
                 else None)
    return tmp_path


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / '.config'))
    monkeypatch.delenv('GIT_CONFIG_GLOBAL', raising=False)
    monkeypatch.setenv('GIT_CONFIG_SYSTEM', str(tmp_path / 'no-such-file'))
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.usefixtures('vocabulary', 'path', 'home', 'no_memoize')
class TestKnownProgramCorrection(object):
    @pytest.mark.parametrize('script, fixed', [
        ('git satus', 'git status'),
        ('git chekout main', 'git checkout main'),
        ('git comit -m x', 'git commit -m x'),
        ('docker pss', 'docker ps'),
        ('npm isntall', 'npm install'),
        ('git dif', 'git diff'),     # a dropped key: git takes no prefix
        ('git statu', 'git status'),
        ('docker pul', 'docker pull'),
    ])
    def test_a_documented_subcommand_one_slip_away(self, script, fixed):
        assert ambient.known_program_correction(script) == fixed

    @pytest.mark.parametrize('script', [
        'git status',            # it is one
        'git st',                # too short a prefix to say which
        'git co',                # of commit and config
        'npm i',                 # npm takes abbreviations
        'npm inst',
        'npm tes',
        'git lg',                # `git-lg` is on PATH
        'git zzzz',              # nothing is close
        'git -C .. satus',       # an option first: left to the tool
        'sudo git satus',        # a wrapper first
        'git satus | less',      # not one simple command
        'git satus && echo ok',
        'ls -la',                # no subcommands documented
        'cat foo',
        'ssh host',
        'git',
        './git satus',
        'FOO=1 git satus',
        'git "satus"',
    ])
    def test_nothing_is_said_unless_certain(self, script):
        assert ambient.known_program_correction(script) is None

    def test_a_git_alias_is_a_command_git_has(self, home):
        (home / '.gitconfig').write_text('[alias]\n\tsatus = status\n')
        assert ambient.known_program_correction('git satus') is None
        assert ambient.known_program_correction('git chekout') == \
            'git checkout'

    def test_an_alias_in_the_repository_counts(self, home):
        (home / '.git').mkdir()
        (home / '.git' / 'config').write_text('[alias]\n\tsatus = status\n')
        assert ambient.known_program_correction('git satus') is None

    def test_an_alias_in_an_included_file_counts(self, home):
        (home / 'aliases').write_text('[alias]\n\tsatus = status\n')
        (home / '.gitconfig').write_text('[include]\n\tpath = aliases\n')
        assert ambient.known_program_correction('git satus') is None

    def test_a_worktree_points_at_its_repository(self, home):
        (home / 'repo').mkdir()
        (home / 'repo' / 'config').write_text('[alias]\n\tsatus = status\n')
        (home / '.git').write_text('gitdir: repo\n')
        assert ambient.known_program_correction('git satus') is None

    def test_an_unreadable_configuration_means_nothing_is_certain(
            self, home, mocker):
        (home / '.gitconfig').write_text('[alias]\n\tsatus = status\n')
        real = ambient.open if hasattr(ambient, 'open') else open

        def refuse(path, *args, **kwargs):
            if str(path).endswith('.gitconfig'):
                raise OSError('refused')
            return real(path, *args, **kwargs)

        mocker.patch('builtins.open', side_effect=refuse)
        assert ambient.git_aliases() is None
        assert ambient.known_program_correction('git satus') is None

    def test_a_docker_plugin_is_a_command_docker_has(self, home, mocker):
        plugins = home / '.docker' / 'cli-plugins'
        plugins.mkdir(parents=True)
        (plugins / 'docker-pss').write_text('')
        assert ambient.known_program_correction('docker pss') is None
        assert ambient.known_program_correction('docker pulll') == \
            'docker pull'

    def test_the_answer_is_quoted_for_the_shell(self, mocker):
        mocker.patch('thebleep.vocabulary.subcommands',
                     return_value=['stat us'])
        assert ambient.known_program_correction('git statu') == \
            "git 'stat us'"


def test_git_aliases_reads_every_file_git_would(home):
    (home / '.config' / 'git').mkdir(parents=True)
    (home / '.config' / 'git' / 'config').write_text('[alias]\n\ta = add\n')
    (home / '.gitconfig').write_text(
        '[core]\n\teditor = vi\n[alias]\n\tb = branch\n[include]\n'
        '\tpath = ~/more\n')
    (home / 'more').write_text('[alias "x"]\n\tc = commit\n')
    assert ambient.git_aliases() == {'a', 'b', 'c'}


def test_git_aliases_without_any_file_is_empty(home):
    assert ambient.git_aliases() == set()
    assert not os.path.exists(str(home / '.gitconfig'))
