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

import json
import importlib
import os
import shutil
import subprocess
import sys
import pytest
from thebleep.shells import Bash
from thebleep.system import Path
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
                 'black', 'cargo', 'prettier', 'pytest', 'mytool', 'bun',
                 'heroku', 'hg', 'make', 'just'):
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

    def test_bun_script_not_found(self, name, payload, canary, tmpdir,
                                  monkeypatch):
        """Script names come out of the repository's own `package.json`.

        Read off disk rather than mocked, because the file is the thing that
        arrives with a clone and JSON will hold any of these names.

        """
        from thebleep.rules import bun_script_not_found

        project = tmpdir.mkdir('bunproj-{}'.format(name))
        project.join('package.json').write(
            json.dumps({'scripts': {payload: 'true'}}))
        monkeypatch.chdir(str(project))

        output = u'error: Script not found "brnch"\n'
        command = Command(u'bun run brnch', output)
        if not bun_script_not_found.match(command):
            return

        suggestions = bun_script_not_found.get_new_command(command)
        assert suggestions, 'the hostile name never reached a suggestion'
        for suggestion in suggestions:
            assert canary(suggestion) == []

    def test_make_target_is_quoted(self, name, payload, canary, tmpdir,
                                   monkeypatch):
        """Static Makefile vocabulary is still untrusted shell input."""
        project = tmpdir.mkdir('make-project')
        project.join('Makefile').write('build&touch:\n\t@true\n')
        monkeypatch.chdir(str(project))
        output = "make: *** No rule to make target 'buil&touch'.  Stop."

        from thebleep.rules import make_no_target

        suggestion = make_no_target.get_new_command(
            Command('make buil&touch', output))[0]
        assert canary(suggestion) == []

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

    def test_git_branch_zero_flag_quotes_a_quoted_branch(self, name, payload,
                                                         canary):
        from thebleep.rules import git_branch_0flag

        command = Command(
            u"git branch '0;'",
            u"fatal: A branch named 'bar' already exists.")

        assert canary(git_branch_0flag.get_new_command(command)) == []

    def test_ls_all_preserves_a_quoted_path(self, name, payload, canary):
        from thebleep.rules import ls_all

        command = Command(u"ls 'a;>LS_ALL'", u'')

        assert canary(ls_all.get_new_command(command)) == []

    def test_unsudo_preserves_a_quoted_argument(self, name, payload, canary):
        from thebleep.rules import unsudo

        command = Command(
            u"sudo echo 'a;>UNSUDO'",
            u'you cannot perform this operation as root')

        assert canary(unsudo.get_new_command(command)) == []

    def test_scm_correction_preserves_a_quoted_argument(self, name, payload,
                                                        canary, mocker):
        from thebleep.rules import scm_correction

        mocker.patch.object(scm_correction, '_get_actual_scm', return_value='hg')
        command = Command(u"git log 'a;>SCM'", u'')

        assert canary(scm_correction.get_new_command(command)) == []

    def test_gradle_wrapper_preserves_a_quoted_argument(self, name, payload,
                                                        canary):
        from thebleep.rules import gradle_wrapper

        command = Command(u"gradle 'a;>GRADLE'", u'')

        assert canary(gradle_wrapper.get_new_command(command)) == []

    def test_prove_recursively_preserves_a_quoted_argument(self, name, payload,
                                                           canary):
        from thebleep.rules import prove_recursively

        command = Command(u"prove 'a;>PROVE'", u'')

        assert canary(prove_recursively.get_new_command(command)) == []

    def test_npm_run_script_preserves_a_quoted_argument(self, name, payload,
                                                        canary):
        from thebleep.rules import npm_run_script

        command = Command(u"npm 'a;>NPM'", u'')

        assert canary(npm_run_script.get_new_command(command)) == []

    def test_dry_preserves_a_quoted_argument(self, name, payload, canary):
        from thebleep.rules import dry

        command = Command(u"echo echo 'a;>DRY'", u'')

        assert canary(dry.get_new_command(command)) == []

    def test_grep_arguments_order_preserves_a_quoted_argument(
            self, name, payload, canary, tmpdir, monkeypatch):
        from thebleep.rules import grep_arguments_order

        tmpdir.join('existing').write('')
        monkeypatch.chdir(str(tmpdir))
        command = Command(
            u"grep 'a;>GREP' existing",
            u'grep: existing: No such file or directory')

        assert canary(grep_arguments_order.get_new_command(command)) == []

    def test_ln_s_order_preserves_quoted_operands(
            self, name, payload, canary, tmpdir, monkeypatch):
        from thebleep.rules import ln_s_order

        tmpdir.join('existing').write('')
        monkeypatch.chdir(str(tmpdir))
        command = Command(
            u"ln -s 'a;>LN' existing",
            u'ln: existing: File exists')

        assert canary(ln_s_order.get_new_command(command)) == []

    def test_git_flag_after_filename_preserves_a_quoted_argument(
            self, name, payload, canary):
        from thebleep.rules import git_flag_after_filename

        command = Command(
            u"git log 'a;>GITFLAG' -p",
            u"fatal: bad flag '-p' used after filename")

        assert canary(git_flag_after_filename.get_new_command(command)) == []

    def test_systemctl_preserves_a_quoted_argument(self, name, payload, canary):
        from thebleep.rules import systemctl

        command = Command(
            u"systemctl 'a;>SYSTEMCTL' start",
            u"Unknown operation 'a'.")

        assert canary(systemctl.get_new_command(command)) == []

    def test_ls_lah_preserves_a_quoted_argument(self, name, payload, canary):
        from thebleep.rules import ls_lah

        command = Command(u"ls 'a;>LSLAH'", u'')

        assert canary(ls_lah.get_new_command(command)) == []

    def test_brew_uninstall_preserves_a_quoted_argument(
            self, name, payload, canary):
        from thebleep.rules import brew_uninstall

        command = Command(
            u"brew uninstall 'a;>BREWUNINSTALL'",
            u"brew uninstall --force")

        assert canary(brew_uninstall.get_new_command(command)) == []

    def test_brew_link_preserves_a_quoted_argument(self, name, payload, canary):
        from thebleep.rules import brew_link

        command = Command(
            u"brew link 'a;>BREWLINK'",
            u"brew link --overwrite")

        assert canary(brew_link.get_new_command(command)) == []

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

    def test_commander_suggestion(self, name, payload, canary):
        """commander.js lists what it thinks you meant, and we repeat one back.

        From [#4](https://github.com/stamparm/thebleep/pull/4).

        """
        from thebleep.rules import commander_suggestion

        output = (u"error: unknown command 'bulid'\n"
                  u"(Did you mean {})?\n".format(payload))
        command = Command(u'mytool bulid', output)
        if not commander_suggestion.match(command):
            return
        for suggestion in commander_suggestion.get_new_command(command):
            assert canary(suggestion) == []

    def test_argparse_invalid_choice(self, name, payload, canary):
        """argparse lists every choice it accepts, and we repeat one back.

        From [#5](https://github.com/stamparm/thebleep/pull/5).

        """
        from thebleep.rules import argparse_invalid_choice

        output = (u"mytool: error: argument sub: invalid choice: 'bulid' "
                  u"(choose from 'install', '{}')\n".format(payload))
        command = Command(u'mytool bulid', output)
        if not argparse_invalid_choice.match(command):
            return
        for suggestion in argparse_invalid_choice.get_new_command(command):
            assert canary(suggestion) == []

    def test_mercurial_preserves_a_quoted_argument(self, name, payload,
                                                   canary):
        from thebleep.rules import mercurial
        from thebleep.shells import shell

        output = (u"hg: unknown command 'brnch'\n"
                  u'(did you mean one of branch, branches?)')
        command = Command(u'hg brnch {}'.format(shell.quote(payload)), output)
        assert canary(mercurial.get_new_command(command)) == []

    def test_git_stash_preserves_a_quoted_argument(self, name, payload,
                                                   canary):
        from thebleep.rules import git_fix_stash
        from thebleep.shells import shell

        command = Command(u'git stash {}'.format(shell.quote(payload)),
                          u'usage: git stash list [<options>]')
        assert canary(git_fix_stash.get_new_command(command)) == []

    def test_git_push_preserves_a_quoted_global_option(self, name, payload,
                                                       canary):
        from thebleep.rules import git_push
        from thebleep.shells import shell

        output = (u'fatal: The current branch master has no upstream branch.\n'
                  u'    git push --set-upstream origin master\n')
        command = Command(u'git -c {}'.format(shell.quote(
            u'user.name=' + payload)) + u' push', output)
        assert canary(git_push.get_new_command(command)) == []

    def test_man_preserves_a_quoted_page(self, name, payload, canary):
        from thebleep.rules import man
        from thebleep.shells import shell

        command = Command(u'man {}'.format(shell.quote(payload)),
                          u'some other output')
        for suggestion in man.get_new_command(command):
            assert canary(suggestion) == []

    def test_sudo_path_name_is_quoted(self, name, payload, canary, mocker):
        from thebleep.rules import sudo_command_from_user_path
        from thebleep.shells import shell

        mocker.patch.object(sudo_command_from_user_path, 'which',
                            return_value='/bin/{}'.format(payload))
        output = u'sudo: {}: command not found'.format(payload)
        command = Command(u'sudo {}'.format(shell.quote(payload)), output)
        assert canary(sudo_command_from_user_path.get_new_command(command)) == []

    def test_git_two_dashes_quotes_the_option(self, name, payload, canary):
        if ' ' in payload or '`' in payload:
            return
        from thebleep.rules import git_two_dashes

        option = u'--{}'.format(payload)
        output = u'error: did you mean `{}` (with two dashes)?'.format(option)
        command = Command(u'git -{}'.format(payload), output)
        assert canary(git_two_dashes.get_new_command(command)) == []

    def test_terraform_suggestion_is_quoted(self, name, payload, canary):
        if '"' in payload:
            return
        from thebleep.rules import terraform_no_command

        output = (u'Terraform has no command named "appyl". '
                  u'Did you mean "{}"?'.format(payload))
        command = Command(u'terraform appyl', output)
        assert canary(terraform_no_command.get_new_command(command)) == []

    def test_go_suggestion_is_quoted(self, name, payload, canary, mocker):
        from thebleep.rules import go_unknown_command

        mocker.patch.object(go_unknown_command, 'get_closest',
                            return_value=payload)
        command = Command(u'go bulid', u'go bulid: unknown command')
        assert canary(go_unknown_command.get_new_command(command)) == []


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
def test_learned_correction_quotes_its_replacement(
        canary, mocker, settings, tmpdir, monkeypatch, set_shell):
    """A learned word is still shell text when it is offered again."""
    from thebleep import learning

    set_shell(Bash)
    settings.user_dir = Path(str(tmpdir))
    monkeypatch.chdir(str(tmpdir))
    assert learning.remember_pending(
        'corpctl deply', "corpctl 'deploy;>LEARNED'",
        cwd=str(tmpdir), shell_name='bash')
    assert learning.learn_last() is not None

    suggestion = list(learning.corrections(
        Command('corpctl deply', '')))[0].script

    assert canary(suggestion) == []


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
def test_cd_correction_quotes_hostile_dir(
        canary, mocker, tmpdir, monkeypatch):
    from thebleep.rules import cd_correction

    monkeypatch.chdir(str(tmpdir))
    hostile = u'folder$(>CD_CORRECTION)'
    mocker.patch.object(cd_correction, '_get_sub_dirs',
                        return_value=[hostile])
    mocker.patch.object(cd_correction, 'get_close_matches',
                        return_value=[hostile])

    suggestion = cd_correction.get_new_command(Command('cd folder', ''))
    assert canary(suggestion) == []


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
@pytest.mark.parametrize('name, command, output', [
    ('yarn', Command('yarn install redux', ''),
     'Run "yarn add redux;>YARN_REPLACED" instead.'),
    ('heroku', Command('heroku log', ''),
     'Run heroku _ to run heroku logs;>HEROKU.'),
    ('hg', Command('hg brnch', ''),
     "hg: unknown command 'brnch'\n"
     '(did you mean one of branch;>HG?)')])
def test_complete_suggestions_quote_output_words(name, command, output, canary):
    module = importlib.import_module('thebleep.rules.' + {
        'yarn': 'yarn_command_replaced',
        'heroku': 'heroku_not_command',
        'hg': 'mercurial'}[name])
    command = Command(command.script, output)

    assert module.match(command)
    assert canary(module.get_new_command(command)) == []


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
def test_git_clone_url_is_quoted(canary):
    from thebleep.rules import git_clone_missing

    command = Command(
        u'https://github.com/stamparm/thebleep.git;>GIT_CLONE',
        u'not found')

    assert git_clone_missing.match(command)
    assert canary(git_clone_missing.get_new_command(command)) == []
