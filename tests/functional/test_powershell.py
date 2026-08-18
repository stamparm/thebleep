# -*- coding: utf-8 -*-

"""PowerShell's half of the integration, run by a real PowerShell.

We claim PowerShell support, and the pieces of it that unit tests cannot judge
are exactly the ones that were wrong: whether a chained correction runs its
second half, whether a quoted argument arrives as one argument, and whether the
alias leaves the session's environment as it found it.

Run with `--enable-functional`; needs docker, and pulls
mcr.microsoft.com/powershell. Windows CI covers the same ground against
Windows PowerShell 5.1 without docker.

"""

import re
import shutil
import subprocess
import pytest
from thebleep.shells import Powershell

IMAGE = 'mcr.microsoft.com/powershell:latest'
ANSI = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')


@pytest.fixture(scope='module')
def pwsh():
    if shutil.which('docker') is None:
        pytest.skip('docker is not available')
    if subprocess.call(['docker', 'image', 'inspect', IMAGE],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL) != 0:
        if subprocess.call(['docker', 'pull', IMAGE],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) != 0:
            pytest.skip('could not pull {}'.format(IMAGE))
    return IMAGE


@pytest.fixture
def run(pwsh, tmpdir):
    """Runs PowerShell over the given script and returns what it printed."""
    def go(lines, interactive=False):
        script = tmpdir.join('script.ps1')
        script.write(u'\n'.join(lines) + u'\n')
        arguments = ['-NoProfile']
        if interactive:
            # History is only recorded for commands read from the input stream,
            # and `Get-History` is how the alias finds the previous command.
            arguments += ['-NonInteractive', '-Command', '-']
            source = script.open('rb')
        else:
            arguments += ['-File', '/w/script.ps1']
            source = None
        try:
            finished = subprocess.run(
                ['docker', 'run', '--rm', '-i',
                 '-v', '{}:/w'.format(str(tmpdir)), '-w', '/w', pwsh,
                 'pwsh'] + arguments,
                stdin=source, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=300)
        finally:
            if source is not None:
                source.close()
        return ANSI.sub('', finished.stdout.decode('utf-8', 'replace'))

    return go


@pytest.fixture
def stub(tmpdir):
    """A `thebleep` that reports what it was given and answers with a fix."""
    fake = tmpdir.join('thebleep')
    fake.write('#!/bin/sh\n'
               'echo "SAW TB_SHELL=$TB_SHELL TB_ALIAS=$TB_ALIAS args=$*" >&2\n'
               'echo "echo corrected"\n')
    fake.chmod(0o755)
    return u'$env:PATH = "/w:" + $env:PATH'


MARK = u'New-Item -ItemType File ./MARK -Force | Out-Null'


@pytest.mark.functional
def test_a_chain_runs_its_second_half(run):
    """`(a) -and (b)` tested whether `a` printed something, not whether it
    worked, so `git add . && git commit` skipped the commit."""
    output = run([Powershell().and_(u"sh -c 'exit 0'", MARK),
                  u'"ran: " + (Test-Path ./MARK)'])
    assert 'ran: True' in output


@pytest.mark.functional
def test_a_chain_stops_when_the_first_half_fails(run):
    output = run([Powershell().and_(u"sh -c 'exit 1'", MARK),
                  u'"ran: " + (Test-Path ./MARK)'])
    assert 'ran: False' in output


@pytest.mark.functional
def test_or_runs_only_after_a_failure(run):
    """What `--repeat` is built out of."""
    output = run([Powershell().or_(u"sh -c 'exit 1'", MARK),
                  u'"after failure: " + (Test-Path ./MARK)',
                  u'Remove-Item -Force ./MARK',
                  Powershell().or_(u"sh -c 'exit 0'", MARK),
                  u'"after success: " + (Test-Path ./MARK)'])
    assert 'after failure: True' in output
    assert 'after success: False' in output


@pytest.mark.functional
def test_a_quoted_argument_arrives_as_one_argument(run):
    """POSIX quoting splits it into three.

    PowerShell does not join adjacent string literals, so `'a'"'"'b'` reaches a
    command as `a`, `'` and `b`.

    """
    value = u"a'b$({})".format(MARK)
    inner = u'for a in "$@"; do echo "[$a]"; done'
    output = run([u"sh -c '{}' _ {}".format(inner, Powershell().quote(value)),
                  u'"pwned: " + (Test-Path ./MARK)'])
    assert u"[{}]".format(value) in output
    assert 'pwned: False' in output


@pytest.mark.functional
def test_the_alias_corrects_and_leaves_nothing_behind(run, stub):
    """Including a correction that starts with `echo`, which used to be
    silently discarded."""
    output = run([stub,
                  Powershell().app_alias(u'bleep'),
                  u'ehco test',
                  u'bleep',
                  u'"TB_SHELL unset after: " + ($null -eq $env:TB_SHELL)',
                  u'"TB_ALIAS unset after: " + ($null -eq $env:TB_ALIAS)',
                  u'exit'], interactive=True)
    assert 'SAW TB_SHELL=powershell TB_ALIAS=bleep args=ehco test' in output
    assert 'corrected' in output
    assert 'TB_SHELL unset after: True' in output
    assert 'TB_ALIAS unset after: True' in output
