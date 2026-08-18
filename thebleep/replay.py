# -*- encoding: utf-8 -*-

"""Whether the previous command may be run a second time.

Reading what a command printed means running it again, because a shell keeps no
record of its own output. For `ls /nowhere` that costs nothing. For `reboot`, a
`git push`, a deploy script or anything that writes a file, it happens twice —
and the second time before the user has agreed to anything, or even been shown
a correction.

Nothing here tries to work out whether a command is *destructive*. That question
has no dependable answer, and a list of dangerous commands would only say that
the ones nobody thought of are safe. The question asked instead is much
narrower, and fails towards asking rather than running:

    can running this again have any effect at all?

Two cases answer no with certainty. Everything else gets a prompt.

"""

import os
import re
from . import logs
from .conf import settings

# A program name is only worth looking up when it is exactly what `sh` will
# run. `$X`, `"deploy"`, `\deploy`, `~/bin/deploy` and `depl*y` each name
# something other than what they look like, and looking the literal text up on
# PATH finds nothing — which would read as "there is nothing to run".
LITERAL_PROGRAM = re.compile(r'^[\w./+:@,-]+$')

# Shell syntax that redirects, chains, substitutes or backgrounds. With any of
# it present the script is no longer one call to one program, so the program's
# name says nothing about what the script would do: `ls > f` writes, `x; rm y`
# removes, `$(deploy)` and `` `deploy` `` run something else entirely.
EFFECTIVE_SYNTAX = ('>', '<', '|', '&', ';', '(', ')', '`', '\n', '\r')

# `sh` finds these without consulting PATH and they run whatever they are
# handed, so "no such program" does not mean "does nothing" for them.
EXECUTING_BUILTINS = frozenset({
    '.', 'source', 'eval', 'exec', 'command', 'builtin', 'trap',
})

# Commands that only read, whatever arguments they are given.
#
# The bar for being on this list is that no combination of flags makes the
# command change anything. That is why `sort` (`-o`), `sed` (`-i`), `awk`
# (`print >`), `find` (`-delete`, `-exec`), `tree` (`-o`), `yq` (`-i`), `date`
# (`-s`), `hostname` (sets it) and `env` (runs a command) are absent despite
# reading in their usual form.
#
# It is also why nothing here is a subcommand dispatcher. Whether `git`,
# `docker`, `npm` or `systemctl` writes depends on the subcommand and its
# flags — `git branch` reads, `git branch -d` deletes — and a list that got
# that distinction subtly wrong would be worse than no list at all, because it
# would run the dangerous cases without asking.
READ_ONLY = frozenset({
    'ack', 'ag', 'apropos', 'arch', 'base32', 'base64', 'basename', 'bat',
    'cal', 'cat', 'cksum', 'cmp', 'column', 'comm', 'cut', 'df', 'diff',
    'dirname', 'du', 'echo', 'egrep', 'expand', 'expr', 'false', 'fgrep',
    'file', 'fmt', 'fold', 'free', 'getconf', 'grep', 'groups', 'head',
    'hexdump', 'id', 'info', 'jq', 'ldd', 'less', 'locale', 'ls', 'lsblk',
    'lscpu', 'lsmod', 'lspci', 'lsusb', 'man', 'md5sum', 'more', 'nl', 'nm',
    'objdump', 'od', 'paste', 'pgrep', 'printenv', 'printf', 'ps', 'pstree',
    'pwd', 'readelf', 'readlink', 'realpath', 'rev', 'rg', 'sha1sum',
    'sha256sum', 'sha512sum', 'size', 'stat', 'strings', 'tac', 'tail',
    'tldr', 'tr', 'true', 'type', 'uname', 'unexpand', 'uniq', 'uptime',
    'users', 'vdir', 'vmstat', 'w', 'wc', 'whatis', 'whereis', 'which', 'who',
    'whoami', 'xxd', 'zcat', 'zgrep',
})


def _program(script):
    """The one program `script` would run, or `None` if it isn't that simple.

    The script is the expanded one, so a shell alias has already been resolved
    into whatever it stands for. Shell *functions* are not expanded, but the
    rerun goes through a non-interactive `sh` that never loads them, so the
    program named here really is the one that would run.

    """
    if any(syntax in script for syntax in EFFECTIVE_SYNTAX):
        return None

    words = script.split()
    if not words:
        return None

    # `FOO=bar cmd` sets FOO for cmd; the assignments are not the command.
    from .utils import command_word_index

    words = words[command_word_index(words):]
    if not words:
        # Assignments and nothing else, which a subshell throws away.
        return ''

    if not LITERAL_PROGRAM.match(words[0]):
        return None

    return words[0]


def is_inert(script):
    """Whether running `script` again cannot have any effect.

    Only two things are certain enough to skip asking about:

    - the program is not there to run, so the shell will fail to find it a
      second time exactly as it did the first;
    - the program only ever reads, whatever it is asked to do.

    """
    program = _program(script)
    if program is None:
        return False
    if program == '':
        return True

    name = os.path.basename(program)
    if name in EXECUTING_BUILTINS or program in EXECUTING_BUILTINS:
        return False
    if name in READ_ONLY:
        return True

    from .utils import which

    return which(program) is None


def _ask(script):
    """Asks whether the command may run again. Only `y` means yes."""
    from .system import get_key

    logs.confirm_replay(script)
    key = get_key()
    answered_yes = key.lower() == 'y'
    logs.replay_answer(answered_yes)
    return answered_yes


def is_allowed(script, expanded):
    """Whether the previous command may be run again to read its output.

    :type script: str
    :type expanded: str
    :rtype: bool

    """
    if is_inert(expanded):
        logs.debug(u'Replay: {} cannot have an effect, running it'.format(
            expanded))
        return True

    if not settings.confirm_replay:
        logs.debug(u'Replay: not asking, confirm_replay is off')
        return True

    from .ui import is_interactive

    if not is_interactive():
        logs.debug(u'Replay: nobody to ask, not running {}'.format(expanded))
        logs.warn(
            u"Not running `{}` again to read its output: there is no terminal "
            u"to ask on. Use --yes to allow it.".format(script))
        return False

    return _ask(script)
