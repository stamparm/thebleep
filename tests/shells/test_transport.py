# -*- coding: utf-8 -*-

"""What the generated alias does to the shell it is defined in.

These run the real shell rather than reading the generated code, because the
things worth being sure of -- that nothing is left exported, that an
over-long history entry does not break the alias -- are properties of the
shell's behaviour and not of the text.

"""

import os
import shutil
import subprocess
import sys
import pytest
from thebleep import const
from thebleep.shells import Bash, Zsh

# A stand-in for `thebleep` that reports what it was handed and answers with a
# correction, so the alias runs all the way through.
FAKE = u"""#!/bin/sh
{
  echo "@@ environment:"
  env | sed 's/=.*//' | grep '^TB_' | sort
  echo "@@ history-bytes: ${#TB_HISTORY}"
  echo "@@ history-last: $(printf '%s\\n' "$TB_HISTORY" | tail -n 1)"
} >&2
echo "echo corrected"
"""

SHELLS = {
    'bash': (Bash, u'history -s'),
    'zsh': (Zsh, u'print -s'),
}


def _run(name, history, tmpdir):
    """Defines the alias in a real `name`, runs it, and reports what happened."""
    binary = shutil.which(name)
    if binary is None:
        pytest.skip('{} is not installed'.format(name))

    fake = tmpdir.join('thebleep')
    fake.write(FAKE)
    os.chmod(str(fake), 0o755)

    shell_class, remember = SHELLS[name]
    script = tmpdir.join('script')
    script.write(u'\n'.join(
        [u'eval "$(cat {})"'.format(tmpdir.join('alias')),
         u'alias ll="ls -alF"']
        + [u'{} {}'.format(remember, entry) for entry in history]
        + [u'bleep',
           u'echo "@@ exit: $?"',
           u'echo "@@ exported: $(env | grep -c \'^TB_\' || true)"',
           u'echo "@@ left: $(set | grep -cE \'^TB_[A-Z]+=\' || true)"']))
    tmpdir.join('alias').write(shell_class().app_alias('bleep'))

    environment = dict(os.environ,
                       PATH='{}{}{}'.format(str(tmpdir), os.pathsep,
                                            os.environ['PATH']))
    finished = subprocess.run(
        [binary, str(script)], cwd=str(tmpdir), env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = finished.stdout.decode('utf-8', 'replace')
    return output, dict(
        line[3:].split(': ', 1)
        for line in output.split('\n') if line.startswith('@@ ') and ': ' in line)


@pytest.mark.skipif(sys.platform == 'win32', reason='needs a POSIX shell')
@pytest.mark.parametrize('name', sorted(SHELLS))
class TestAliasTransport(object):
    def test_the_correction_runs(self, name, tmpdir):
        output, _ = _run(name, [u'"gti status"'], tmpdir)
        assert 'corrected' in output

    def test_the_shell_state_reaches_us(self, name, tmpdir):
        output, reported = _run(name, [u'"gti status"'], tmpdir)
        assert 'TB_SHELL' in output
        assert 'TB_ALIAS' in output
        assert 'TB_SHELL_ALIASES' in output
        assert 'gti status' in reported['history-last']

    def test_nothing_is_left_exported(self, name, tmpdir):
        """The user's alias list is not every later command's business."""
        _, reported = _run(name, [u'"gti status"'], tmpdir)
        assert reported['exported'] == '0'

    def test_nothing_is_left_in_the_shell(self, name, tmpdir):
        _, reported = _run(name, [u'"gti status"'], tmpdir)
        assert reported['left'] == '0'

    def test_an_enormous_history_entry_does_not_break_the_alias(self, name,
                                                                tmpdir):
        """One pasted command used to break every correction after it.

        The environment a program can be handed is bounded, and going over the
        bound makes the alias fail with "Argument list too long" until the entry
        falls out of the history window.

        Refs: nvbn/thefuck#798

        """
        huge = u'"echo {}"'.format(u'A' * (const.TRANSPORT_LIMIT * 2))
        output, reported = _run(name, [huge, u'"gti status"'], tmpdir)
        assert 'too long' not in output
        assert 'corrected' in output
        assert int(reported['history-bytes']) < const.TRANSPORT_LIMIT
