# -*- coding: utf-8 -*-

"""What the alias does with a correction the user asked to edit.

Driven through a pty running the real shell, because a line editor is the one
thing that only exists in front of a terminal. Reading the generated code would
say nothing about the question worth asking: does the correction end up
somewhere the user can change it, and does the changed version -- not the
suggested one -- run?

The stand-in for `thebleep` prints a correction and exits with `EXIT_EDIT`,
which is exactly what the real one does when tab is pressed.

Each shell here is skipped when it is not installed, so a machine with only
bash still checks bash. `tests/Dockerfile` has the rest of them.

"""

import os
import shutil
import subprocess
import sys
import pytest
from thebleep import const
from thebleep.shells import Bash, Fish, Zsh

pexpect = pytest.importorskip('pexpect')

PROMPT = u'@@> '
TIMEOUT = 20


class Under(object):
    """How to get one shell to a prompt with the alias defined."""

    __slots__ = ('name', 'shell_class', 'arguments', 'prompt', 'source',
                 'keeps_variables')

    def __init__(self, name, shell_class, arguments, prompt, source,
                 keeps_variables=True):
        self.name = name
        self.shell_class = shell_class
        self.arguments = arguments
        self.prompt = prompt
        self.source = source
        self.keeps_variables = keeps_variables


SHELLS = {
    shell.name: shell for shell in [
        Under('bash', Bash, ['--norc', '--noprofile', '-i'],
              u"PS1='{}'".format(PROMPT), u'eval "$(cat {})"'),
        Under('zsh', Zsh, ['-f', '-i'],
              u"PS1='{}'".format(PROMPT), u'eval "$(cat {})"'),
        # Fish keeps no shell variables around to leak: the alias hands the
        # transport to `thebleep` through `env`, so there is nothing to unset.
        Under('fish', Fish, ['--no-config', '-i'],
              u"function fish_prompt; echo -n '{}'; end".format(PROMPT),
              u'source {}', keeps_variables=False),
    ]
}

# Prints a correction and asks for it to be edited rather than run.
FAKE = u"""#!/bin/sh
echo 'echo AAA'
exit {}
""".format(const.EXIT_EDIT)

# Prints a correction to be run, which is the ordinary path.
FAKE_RUNS = u"""#!/bin/sh
echo 'echo RAN-AAA'
exit 0
"""

# Reports what the alias decided about editing, the way the real one reads it.
FAKE_REPORTS = u"""#!/bin/sh
echo "CAN_EDIT=[$TB_CAN_EDIT]" 1>&2
echo 'echo RANMARK'
exit 0
"""


def _bash_can_edit():
    """Whether the bash on this machine has the `read -e -i` the branch needs.

    It arrived in bash 4.0, and macOS still ships 3.2.57 -- where `read -i` is
    "invalid option". The alias works this out for itself and never tells The
    Bleep that editing is available, so the feature is correct there; what
    cannot be exercised is the branch, because the stand-in for `thebleep` below
    asks for editing whatever the shell said.

    """
    binary = shutil.which('bash')
    if binary is None:
        return False
    try:
        reported = subprocess.check_output(
            [binary, '-c', 'echo ${BASH_VERSINFO[0]}'],
            stderr=subprocess.DEVNULL).decode('utf-8', 'replace')
        return int(reported.strip()) >= 4
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def _can_edit(name):
    return _bash_can_edit() if name == 'bash' else True


def _spawn(name, tmpdir, fake_source):
    under = SHELLS[name]
    binary = shutil.which(name)
    if binary is None:
        pytest.skip('{} is not installed'.format(name))

    fake = tmpdir.join('thebleep')
    fake.write(fake_source)
    os.chmod(str(fake), 0o755)

    alias = tmpdir.join('alias')
    alias.write_text(under.shell_class().app_alias('bleep'), 'utf-8')

    environment = dict(os.environ,
                       LC_ALL='C.UTF-8', LANG='C.UTF-8', TERM='dumb',
                       PATH='{}{}{}'.format(str(tmpdir), os.pathsep,
                                            os.environ['PATH']))
    proc = pexpect.spawnu(binary, under.arguments, cwd=str(tmpdir),
                          env=environment, timeout=TIMEOUT)
    proc.sendline(under.prompt)
    proc.expect_exact(PROMPT)
    proc.sendline(under.source.format(alias))
    proc.expect_exact(PROMPT)
    return proc


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
@pytest.mark.parametrize('name', sorted(SHELLS))
class TestEditBuffer(object):
    def test_the_correction_is_offered_for_editing(self, name, tmpdir):
        """It arrives on a line the user is editing, and has not run."""
        if not _can_edit(name):
            pytest.skip('this {} cannot edit; see TestTheAliasKnowsWhatItCanDo'
                        .format(name))
        proc = _spawn(name, tmpdir, FAKE)
        proc.sendline(u'bleep')
        proc.expect_exact(u'echo AAA')
        # Nothing ran: `echo AAA` would have printed AAA on a line of its own.
        proc.sendline(u'')
        proc.expect_exact(u'AAA')
        proc.close(force=True)

    def test_the_edited_command_is_what_runs(self, name, tmpdir):
        """The suggestion is a starting point, not what gets executed."""
        if not _can_edit(name):
            pytest.skip('this {} cannot edit; see TestTheAliasKnowsWhatItCanDo'
                        .format(name))
        proc = _spawn(name, tmpdir, FAKE)
        proc.sendline(u'bleep')
        proc.expect_exact(u'echo AAA')
        proc.send(u'BBB')
        proc.sendline(u'')
        proc.expect_exact(u'AAABBB')
        proc.close(force=True)

    def test_running_a_correction_still_works(self, name, tmpdir):
        """The ordinary path is untouched by the branch beside it."""
        proc = _spawn(name, tmpdir, FAKE_RUNS)
        proc.sendline(u'bleep')
        proc.expect_exact(u'RAN-AAA')
        proc.close(force=True)

    def test_the_alias_leaves_nothing_behind(self, name, tmpdir):
        """Including after the edit branch, which has variables of its own."""
        if not SHELLS[name].keeps_variables:
            pytest.skip('{} sets no shell variables to leave behind'
                        .format(name))
        if not _can_edit(name):
            pytest.skip('this {} cannot edit; see TestTheAliasKnowsWhatItCanDo'
                        .format(name))
        proc = _spawn(name, tmpdir, FAKE)
        proc.sendline(u'bleep')
        proc.expect_exact(u'echo AAA')
        proc.sendline(u'')
        proc.expect_exact(u'AAA')
        proc.sendline(u'echo "left: $(set | grep -cE \'^TB_[A-Z]+=\')"')
        proc.expect_exact(u'left: 0')
        proc.close(force=True)


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
class TestTheAliasKnowsWhatItCanDo(object):
    """Whether editing is offered is the alias's decision, in the real shell.

    This is the half that matters on a machine whose bash is too old: the
    feature is correct there precisely because the alias never advertises it, so
    The Bleep never hands back a command the shell could not put anywhere.

    """

    @pytest.mark.parametrize('name', sorted(SHELLS))
    def test_it_says_so_only_when_it_can(self, name, tmpdir):
        proc = _spawn(name, tmpdir, FAKE_REPORTS)
        proc.sendline(u'bleep')
        expected = u'CAN_EDIT=[1]' if _can_edit(name) else u'CAN_EDIT=[]'
        proc.expect_exact(expected)
        proc.close(force=True)

    def test_bash_four_is_where_read_i_arrived(self):
        """A statement of the fact the alias's test encodes, so that a machine
        with an older bash reads as a skip rather than as a mystery."""
        assert _bash_can_edit() == _can_edit('bash')
