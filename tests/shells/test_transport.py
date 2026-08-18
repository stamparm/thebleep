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
  echo "@@ history-chars: ${#TB_HISTORY}"
  echo "@@ history-bytes: $(printf '%s' "$TB_HISTORY" | wc -c | tr -d ' ')"
  echo "@@ history-last: $(printf '%s\\n' "$TB_HISTORY" | tail -n 1)"
} >&2
echo "echo corrected"
"""

SHELLS = {
    'bash': (Bash, u'history -s'),
    'zsh': (Zsh, u'print -s'),
}

# What the kernel refuses to exceed for any one environment variable:
# MAX_ARG_STRLEN, thirty-two pages. The test entry is sized against this and not
# against `TRANSPORT_LIMIT`, because a test that scales with the thing it is
# checking cannot fail: sized as a multiple of the cap, every entry is over the
# cap by construction and gets trimmed whatever the cap is.
ONE_VARIABLE_LIMIT = 128 * 1024


def _history_reaches_us(name, tmpdir):
    """Whether this shell hands us any history in this harness at all.

    A non-interactive shell records history only if it feels like it, and the
    ones here disagree: bash 3.2, which is what macOS ships, gives back nothing
    for `history -s` followed by `fc -ln`, and a non-interactive zsh does not
    number events so `fc -ln -N` cannot pick a window. That is the harness, not
    the alias -- what the shell hands over in a real terminal is covered by the
    functional tests, which drive one.

    So the assertions that need history present are skipped where it is not,
    rather than passing for the wrong reason.

    """
    _, reported = _run(name, [u'"a probe command"'], tmpdir.mkdir('probe'))
    return int(reported.get('history-chars', 0)) > 0


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
    script.write_text(u'\n'.join(
        [u'eval "$(cat {})"'.format(tmpdir.join('alias')),
         u'alias ll="ls -alF"']
        + [u'{} {}'.format(remember, entry) for entry in history]
        + [u'bleep',
           u'echo "@@ exit: $?"',
           u'echo "@@ exported: $(env | grep -c \'^TB_\' || true)"',
           u'echo "@@ left: $(set | grep -cE \'^TB_[A-Z]+=\' || true)"']),
        'utf-8')
    tmpdir.join('alias').write_text(shell_class().app_alias('bleep'),
                                    'utf-8')

    environment = dict(os.environ,
                       LC_ALL='C.UTF-8', LANG='C.UTF-8',
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
        if not _history_reaches_us(name, tmpdir):
            pytest.skip('{} keeps no history in a non-interactive shell'
                        .format(name))
        assert 'gti status' in reported['history-last']

    def test_nothing_is_left_exported(self, name, tmpdir):
        """The user's alias list is not every later command's business."""
        _, reported = _run(name, [u'"gti status"'], tmpdir)
        assert reported['exported'] == '0'

    def test_nothing_is_left_in_the_shell(self, name, tmpdir):
        _, reported = _run(name, [u'"gti status"'], tmpdir)
        assert reported['left'] == '0'

    @pytest.mark.parametrize('character, wide', [
        (u'A', 'one byte per character'),
        (u'\u4e2d', 'three bytes per character'),
        (u'\U0001f600', 'four bytes per character'),
    ])
    def test_an_enormous_history_entry_does_not_break_the_alias(
            self, name, character, wide, tmpdir):
        """One pasted command used to break every correction after it.

        The environment a program can be handed is bounded, and going over the
        bound makes the alias fail with "Argument list too long" until the entry
        falls out of the history window.

        The wide characters are the ones that caught this out. `${#var}` in bash
        and zsh counts characters and the kernel counts bytes, so a cap of 65536
        characters was satisfied by a single 64000-character command of
        three-byte characters -- 192000 bytes -- which then failed to exec
        anyway, in both shells.

        Refs: nvbn/thefuck#798

        """
        # Forty percent more bytes than one variable can hold, however many
        # characters that takes. Deliberately not far more: the wide cases have
        # to stay under a *character* count that a byte limit would reject, which
        # is the gap the bug lived in.
        count = (ONE_VARIABLE_LIMIT * 7 // 5) // len(character.encode('utf-8'))
        huge = u'"echo {}"'.format(character * count)
        output, reported = _run(name, [huge, u'"gti status"'], tmpdir)

        assert 'too long' not in output.lower(), wide
        if not _history_reaches_us(name, tmpdir):
            # Otherwise there was nothing oversized to trim and this would pass
            # for the wrong reason.
            pytest.skip('{} keeps no history in a non-interactive shell'
                        .format(name))
        # The huge entry is still the one before last, so this also says that it
        # does not stay broken while that command is recent.
        assert 'corrected' in output
        assert int(reported['history-chars']) < const.TRANSPORT_LIMIT
        # What exec is actually given, which is the limit that matters.
        assert int(reported['history-bytes']) < 128 * 1024
