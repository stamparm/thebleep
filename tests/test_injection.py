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
                 'sh', 'env', 'rm', 'kill', 'ssh', 'ssh-keygen', 'vim',
                 'rails', 'kubectl', 'uv', 'ruff', 'gh', 'helm',
                 'black', 'cargo', 'pytest', 'mytool'):
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

    # Reported as stamparm/thebleep#2, with a working proof of concept: a branch
    # name reaches these through git's own hint, and only whitespace, control
    # characters and `~^:?*[\\` are illegal in a ref name -- so `;`, `$()`, a
    # backtick, `&`, `|` and `#` are all fair game for whoever named the branch.
    # Three of them were reported; `git_help_aliased`, `git_merge` and `fix_file`
    # turned up in the sweep that followed.
    def test_git_push_set_upstream(self, name, payload, canary):
        """git's `--set-upstream` hint, which has the branch name in it."""
        from thebleep.rules import git_push

        output = (u'fatal: The current branch {0} has no upstream branch.\n'
                  u'To push the current branch and set the remote as upstream, '
                  u'use\n\n    git push --set-upstream origin {0}\n'.format(payload))
        command = Command(u'git push', output)
        if not git_push.match(command):
            return
        assert canary(git_push.get_new_command(command)) == []

    def test_git_push_different_branch_names(self, name, payload, canary):
        """A whole `git push <remote> <branch>` line, repeated back."""
        from thebleep.rules import git_push_different_branch_names as rule

        output = (u'error: The upstream branch of your current branch does not '
                  u'match\nthe name of your current branch.  To push to the '
                  u'upstream branch\non the remote, use\n\n'
                  u'    git push origin {0}\n'.format(payload))
        command = Command(u'git push', output)
        if not rule.match(command):
            return
        assert canary(rule.get_new_command(command)) == []

    def test_git_pull_set_upstream_to(self, name, payload, canary):
        """The branch name arrives twice in this one."""
        from thebleep.rules import git_pull

        output = (u'There is no tracking information for the current branch.\n'
                  u'\n    git pull <remote> <branch>\n\nIf you wish to set '
                  u'tracking information for this branch you can do so with:'
                  u'\n\n    git branch --set-upstream-to=origin/<branch> {0}'
                  u'\n\n'.format(payload))
        command = Command(u'git pull', output)
        if not git_pull.match(command):
            return
        assert canary(git_pull.get_new_command(command)) == []

    def test_git_help_aliased(self, name, payload, canary):
        """An alias out of the `.git/config` of a repository you cloned."""
        from thebleep.rules import git_help_aliased

        output = u"`git st' is aliased to `{}'".format(payload)
        command = Command(u'git help st', output)
        if not git_help_aliased.match(command):
            return
        assert canary(git_help_aliased.get_new_command(command)) == []

    def test_git_merge(self, name, payload, canary):
        """A branch name that came from the remote."""
        from thebleep.rules import git_merge

        output = (u'merge: feature - not something we can merge\n\n'
                  u'Did you mean this?\n\t{}\n'.format(payload))
        command = Command(u'git merge feature', output)
        if not git_merge.match(command):
            return
        assert canary(git_merge.get_new_command(command)) == []

    def test_yarn_alias(self, name, payload, canary):
        from thebleep.rules import yarn_alias

        output = u'Did you mean `yarn {}`'.format(payload)
        command = Command(u'yarn ls', output)
        if not yarn_alias.match(command):
            return
        assert canary(yarn_alias.get_new_command(command)) == []

    def test_rails_migrations_pending(self, name, payload, canary):
        from thebleep.rules import rails_migrations_pending

        output = (u'Migrations are pending. To resolve this issue, run:\n'
                  u'        bin/rails db:migrate {}\n'.format(payload))
        command = Command(u'rails s', output)
        if not rails_migrations_pending.match(command):
            return
        assert canary(rails_migrations_pending.get_new_command(command)) == []

    def test_fix_file(self, name, payload, canary, tmpdir, monkeypatch,
                      settings):
        """A filename, which needs no git at all: cloning a repository or
        unpacking an archive is enough to put one on disk."""
        from thebleep.rules import fix_file

        hostile = tmpdir.mkdir('src-' + name).join(payload + '.py')
        hostile.write('')
        monkeypatch.chdir(hostile.dirpath())
        monkeypatch.setitem(os.environ, 'EDITOR', 'vim')
        settings.fixlinecmd = u'{editor} {file} +{line}'
        settings.fixcolcmd = None

        output = (u'  File "{}.py", line 3\n    x=\n     ^\n'
                  u'SyntaxError: invalid syntax\n'.format(payload))
        command = Command(u'python x.py', output)
        if not fix_file.match(command):
            return
        assert canary(fix_file.get_new_command(command)) == []

    def test_cobra_suggestion(self, name, payload, canary):
        """Any cobra tool lists what it thinks you meant, and we repeat one
        back. One rule for all of them, so one canary covers `kubectl`, `gh`,
        `helm` and every other Go tool."""
        from thebleep.rules import cobra_suggestion

        output = (u'error: unknown command "gat" for "kubectl"\n\n'
                  u'Did you mean this?\n\t{}\n\n'.format(payload))
        command = Command(u'kubectl gat pods', output)
        if not cobra_suggestion.match(command):
            return
        for suggestion in cobra_suggestion.get_new_command(command):
            assert canary(suggestion) == []

    def test_clap_suggestion(self, name, payload, canary):
        """And any clap tool names the answer in its tip.

        clap puts each name in single quotes, so the `QUOTE` payload cannot
        arrive through this route whole -- what is read out of the tip is the
        two halves of it. Both still go to the shell, which is the thing being
        checked.

        """
        from thebleep.rules import clap_suggestion

        output = (u"error: unrecognized subcommand 'piip'\n\n"
                  u"  tip: a similar subcommand exists: '{}'\n\n"
                  u'Usage: uv [OPTIONS] <COMMAND>\n'.format(payload))
        command = Command(u'uv piip install requests', output)
        if not clap_suggestion.match(command):
            return
        for suggestion in clap_suggestion.get_new_command(command):
            assert canary(suggestion) == []

    def test_clap_suggestion_for_an_option(self, name, payload, canary):
        """The same rule corrects mistyped flags, by the same route."""
        from thebleep.rules import clap_suggestion

        output = (u"error: unexpected argument '--fixx' found\n\n"
                  u"  tip: a similar argument exists: '{}'\n".format(payload))
        command = Command(u'ruff check --fixx .', output)
        if not clap_suggestion.match(command):
            return
        for suggestion in clap_suggestion.get_new_command(command):
            assert canary(suggestion) == []

    def test_click_suggestion(self, name, payload, canary):
        """Click names its guesses in one sentence, quoted."""
        from thebleep.rules import click_suggestion

        output = (u"Error: No such option '--chekc'. "
                  u"(Did you mean one of: '{}', '--code'?)\n".format(payload))
        command = Command(u'black --chekc .', output)
        if not click_suggestion.match(command):
            return
        for suggestion in click_suggestion.get_new_command(command):
            assert canary(suggestion) == []

    def test_argparse_invalid_choice(self, name, payload, canary):
        """Python argparse choices list is read from output and quoted."""
        from thebleep.rules import argparse_invalid_choice

        output = (u"mytool: error: argument sub: invalid choice: 'bulid' "
                  u"(choose from install, {})\n".format(payload))
        command = Command(u'mytool bulid', output)
        if not argparse_invalid_choice.match(command):
            return
        for suggestion in argparse_invalid_choice.get_new_command(command):
            assert canary(suggestion) == []
