# -*- coding: utf-8 -*-

"""What a suggestion does when the name in it came from somewhere hostile.

A correction is text that the shell then evaluates, and much of that text is
copied out of somewhere the user does not control: a tool's error message, a
repository's branches, a package file's scripts. Names in those places are
allowed to contain shell syntax -- git will happily make a branch called
`feature;rm -rf ~` -- so every one of them has to be quoted on the way into a
suggestion.

The oracle here is a real shell. Each payload creates a file using nothing but
shell syntax, so detection needs no program on PATH, and PATH is replaced with
stubs before anything runs, so a suggestion cannot do anything else either.

"""

import os
import shutil
import subprocess
import sys
import pytest
from thebleep.shells import Bash
from thebleep.types import Command
from thebleep.utils import replace_command

# Each of these writes a file named after itself, and each starts with the
# characters of the typo so that `get_close_matches` will pick it -- which is
# the mechanism by which a hostile name reaches a suggestion at all.
PAYLOADS = [
    ('CMDSUB', u'brancha$(>CMDSUB)'),
    ('BACKTICK', u'branchb`>BACKTICK`'),
    ('SEMI', u'branchc;>SEMI'),
    ('AND', u'branchd&&>AND'),
    ('PIPE', u'branche|>PIPE'),
    ('REDIR', u'branchf >REDIR'),
    ('QUOTE', u"branchg'>QUOTE'"),
]


@pytest.fixture
def canary(tmpdir):
    """Runs a suggestion where it can only leave evidence, and reports it."""
    stubs = tmpdir.mkdir('bin')
    stub = stubs.join('_stub')
    stub.write('#!/bin/sh\nexit 0\n')
    stub.chmod(0o755)
    for name in ('git', 'az', 'composer', 'grunt', 'npm', 'yarn', 'gradle',
                 'sh', 'env', 'rm', 'kill', 'ssh', 'ssh-keygen'):
        shutil.copy(str(stub), str(stubs.join(name)))

    work = tmpdir.mkdir('work')

    def run(suggestion):
        subprocess.call(['/bin/bash', '-c', suggestion], cwd=str(work),
                        env={'PATH': str(stubs), 'HOME': str(work)},
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL, timeout=30)
        return sorted(os.listdir(str(work)))

    return run


@pytest.fixture(autouse=True)
def bash(set_shell):
    return set_shell(Bash)


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
@pytest.mark.parametrize('name, payload', PAYLOADS)
class TestNamesFromSomewhereElse(object):
    def test_replace_command(self, name, payload, canary):
        """The shared helper behind two dozen `*_no_command` rules."""
        for suggestion in replace_command(
                Command(u'git branch', u''), u'branch', [payload]):
            assert canary(suggestion) == []

    def test_git_checkout_branch_name(self, name, payload, canary, mocker):
        """A branch name out of `git branch`, in a repository you cloned."""
        from thebleep.rules import git_checkout

        mocker.patch('thebleep.rules.git_checkout.get_branches',
                     return_value=[payload])
        output = (u"error: pathspec 'branch' did not match any file(s) "
                  u"known to git")
        for suggestion in git_checkout.get_new_command(
                Command(u'git checkout branch', output)):
            assert canary(suggestion) == []

    def test_git_checkout_pathspec(self, name, payload, canary, mocker):
        """And the fallback, where the name comes out of git's message."""
        from thebleep.rules import git_checkout

        mocker.patch('thebleep.rules.git_checkout.get_branches',
                     return_value=[])
        output = (u"error: pathspec '{}' did not match any file(s) "
                  u"known to git".format(payload))
        command = Command(u'git brunch', output)
        if not git_checkout.match(command):
            return
        for suggestion in git_checkout.get_new_command(command):
            assert canary(suggestion) == []

    def test_git_branch_delete_checked_out(self, name, payload, canary,
                                           mocker):
        """The default branch, which comes from the repository's origin/HEAD."""
        from thebleep.rules import git_branch_delete_checked_out as rule

        mocker.patch.object(rule, '_default_branch', return_value=payload)
        output = (u"error: Cannot delete branch 'x' checked out at "
                  u"'/tmp/wt'")
        assert canary(rule.get_new_command(
            Command(u'git branch -d x', output))) == []

    def test_az_cli(self, name, payload, canary):
        from thebleep.rules import az_cli

        output = (u"'brnch' is misspelled or not recognized by the system.\n"
                  u"Did you mean '{}' ?\n".format(payload))
        for suggestion in az_cli.get_new_command(
                Command(u'az brnch', output)):
            assert canary(suggestion) == []

    def test_composer(self, name, payload, canary):
        from thebleep.rules import composer_not_command

        output = (u'Command "brnch" is not defined.\n\n'
                  u'Did you mean this?\n    {}\n'.format(payload))
        assert canary(composer_not_command.get_new_command(
            Command(u'composer brnch', output))) == []

    def test_grunt(self, name, payload, canary, mocker):
        """Task names come from the repository's own Gruntfile."""
        from thebleep.rules import grunt_task_not_found

        mocker.patch.object(grunt_task_not_found, '_get_all_tasks',
                            return_value=[payload])
        output = u'Warning: Task "brnch" not found.\n'
        assert canary(grunt_task_not_found.get_new_command(
            Command(u'grunt brnch', output))) == []

    def test_ssh_known_hosts(self, name, payload, canary):
        """The known_hosts path and host name come out of ssh's warning."""
        from thebleep.rules import ssh_known_hosts

        output = (u'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!\n'
                  u'Offending ED25519 key in /home/u/{}:2\n'
                  u'Host key for {} has changed\n'.format(payload, payload))
        command = Command(u'ssh user@host', output)
        if not ssh_known_hosts.match(command):
            return
        assert canary(ssh_known_hosts.get_new_command(command)) == []
