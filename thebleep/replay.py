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

    is there a reason to believe running this again does nothing?

One answer is certain: there is no such program, so the shell will fail to find
it a second time exactly as it did the first.

The other is a judgement, and worth stating as one. `READ_ONLY` below is a list
of programs that only read, whatever they are asked to do -- and it is a
judgement about the name, which is not a proof about the program that will run.
A program of that name earlier on `PATH`, or a shell wrapper around it, is
outside anything a name can tell us. What makes it a defensible judgement rather
than a guess is that the same program under the same name already ran once, a
moment earlier, when the user typed it: this decides whether it runs a *second*
time, not whether it is safe.

Everything else gets a prompt.

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

# `sh` finds these without consulting PATH, so "no such program" says nothing
# about them: the first six run whatever they are handed, and `kill` is a
# builtin in every shell even where `/usr/bin/kill` is missing. The rest of the
# builtins only affect the subshell, which is thrown away.
EFFECTIVE_BUILTINS = frozenset({
    '.', 'source', 'eval', 'exec', 'command', 'builtin', 'trap', 'kill',
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
#
# Held to that bar, these did not make it, each having been made to demonstrate
# the effect it is not supposed to be able to have:
#
#   uniq   takes an output file as its second operand and overwrites it
#   file   `-C` compiles a magic file and writes the `.mgc` beside it
#   info   `--output` writes the page to a file
#   less   runs whatever `LESSOPEN` names, on a file that need not even exist
#   man    writes a formatted copy into the cat page cache
#
# and `bat`, `more`, `tldr` and `ldd` went with them: pagers and manual readers
# are the same kind of program as the two above, and `ldd`'s own manual page
# says not to run it on an untrusted executable.
READ_ONLY = frozenset({
    'ack', 'ag', 'apropos', 'arch', 'base32', 'base64', 'basename',
    'cal', 'cat', 'cksum', 'cmp', 'column', 'comm', 'cut', 'df', 'diff',
    'dirname', 'du', 'echo', 'egrep', 'expand', 'expr', 'false', 'fgrep',
    'fmt', 'fold', 'free', 'getconf', 'grep', 'groups', 'head',
    'hexdump', 'id', 'jq', 'locale', 'ls', 'lsblk',
    'lscpu', 'lsmod', 'lspci', 'lsusb', 'md5sum', 'nl', 'nm',
    'objdump', 'od', 'paste', 'pgrep', 'printenv', 'printf', 'ps', 'pstree',
    'pwd', 'readelf', 'readlink', 'realpath', 'rev', 'rg', 'sha1sum',
    'sha256sum', 'sha512sum', 'size', 'stat', 'strings', 'tac', 'tail',
    'tr', 'true', 'type', 'uname', 'unexpand', 'uptime',
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
    """Whether there is reason to believe running `script` again does nothing.

    Two things are worth not asking about:

    - the program is not there to run, so the shell will fail to find it a
      second time exactly as it did the first;
    - the program is one of the ones that only ever read, whatever they are
      asked to do.

    """
    program = _program(script)
    if program is None:
        return False
    if program == '':
        return True

    name = os.path.basename(program)
    if name in EFFECTIVE_BUILTINS or program in EFFECTIVE_BUILTINS:
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

    # Asked about what would actually run, which an alias may have turned into
    # something the user would not recognise from what they typed.
    return _ask(expanded)
