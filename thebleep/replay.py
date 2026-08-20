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

A second is the same certainty one level down. A program that dispatches on a
subcommand does nothing at all until it has recognised one, so a subcommand it
does not have fails at dispatch the second time exactly as it did the first --
and that is the whole of the typo case, which is what a correction is usually
for. What makes this certain rather than a judgement is that the subcommand is
not guessed at here: the program is asked for its own list. See `DISPATCHERS`.

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

# Programs that do nothing whatever until they have recognised a subcommand,
# and the read-only question that makes each one list the subcommands it has.
#
# `git` cannot go on `READ_ONLY` -- `git push` is not a read -- but `git satus`
# is not a `git push` either, and until 4.0.3 the two were treated alike, so
# every mistyped subcommand was a question. The list is asked of git rather
# than written down here on purpose: a hard-coded one would go stale in the
# dangerous direction, a subcommand added later looking unrecognised and its
# command running again unasked.
#
# `--list-cmds` arrived in git 2.18; an older git answers nothing, which asks.
# `alias` is in the list deliberately -- an alias is a subcommand git does have,
# and it can stand for anything at all, including `!deploy.sh`. `cargo --list`
# names its aliases too, including the ones a `config.toml` adds and the `!`
# ones that shell out.
#
# The bar for being here is that the answer is *complete*: every word the
# program will dispatch on has to be in it, because one that is missing looks
# like a typo and its command then runs again unasked. Over-inclusion is
# harmless -- a word taken for a subcommand it is not merely asks -- which is
# why the answer is read as a bag of words rather than parsed. Under-inclusion
# is the whole risk, and it is not a theoretical one:
#
#   npm    `npm help` and `npm -l` both leave the aliases out, so the list has
#          no `i` in it -- and `npm i` installs. It is the single most typed
#          npm command there is.
#   uv     `uv --help` omits its hidden subcommands: `generate-shell-completion`
#          is absent from the list and dispatches perfectly well.
#
# `docker` and `kubectl` are not here for want of a listing that can be shown to
# be complete rather than for want of trying; a `--help` screen is a document
# for a person, and no promise about what the program will accept.
DISPATCHERS = {
    'git': ('--list-cmds=main,others,alias,nohelpers',),
    'cargo': ('--list',),
}

# Long enough for a program to print a list it already knows, short enough that
# nobody waits on it. Whatever does not answer in the time is treated as not
# having answered, which asks.
PROBE_TIMEOUT = 5


def _words(script):
    """The words `sh` would run, or `None` if it isn't that simple.

    The script is the expanded one, so a shell alias has already been resolved
    into whatever it stands for. Shell *functions* are not expanded, but the
    rerun goes through a non-interactive `sh` that never loads them, so the
    program named here really is the one that would run.

    An empty list means assignments and nothing else, which a subshell throws
    away.

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
        return []

    if not LITERAL_PROGRAM.match(words[0]):
        return None

    return words


def _subcommands(program, question):
    """The subcommands `program` says it has, or `None` if it would not say.

    The answer is read as a bag of words, which for `git --list-cmds` is exactly
    the list and for `cargo --list` is the list plus the descriptions beside it.
    Taking a description's words for subcommands costs nothing: a word wrongly
    in the set only means the question gets asked. A word wrongly *out* of it is
    the dangerous direction, and no parsing can put back what the program did
    not print.

    Only a clean answer counts. A program that is not there, fails, times out,
    prints nothing or cannot be run at all returns `None`, and `None` asks.

    """
    import subprocess

    try:
        answer = subprocess.check_output(
            (program,) + question, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, timeout=PROBE_TIMEOUT)
    except Exception:
        logs.debug(u'Replay: {} would not list its subcommands'.format(
            program))
        return None

    names = answer.decode('utf-8', 'replace').split()
    return frozenset(names) if names else None


def _dispatch_fails(program, args):
    """Whether `program` would refuse the subcommand it was given, again.

    Only the plainest form is answered: the subcommand has to be the very next
    word. `git -C /tmp satus` is left to the question, because working out
    which of a program's own options take a value -- and which of the remaining
    words is therefore the subcommand rather than a path -- is exactly the kind
    of nearly-right that would run `git -C /tmp push` a second time unasked.

    """
    name = os.path.basename(program)
    question = DISPATCHERS.get(name)
    if question is None or not args or args[0].startswith('-'):
        return False

    known = _subcommands(program, question)
    if not known:
        # No answer, and an empty one is no answer either: a program that
        # listed nothing would make every subcommand look like a typo.
        return False

    if args[0] in known:
        return False

    logs.debug(u'Replay: {} has no subcommand {}, so it does nothing'.format(
        name, args[0]))
    return True


def is_inert(script):
    """Whether there is reason to believe running `script` again does nothing.

    Three things are worth not asking about:

    - the program is not there to run, so the shell will fail to find it a
      second time exactly as it did the first;
    - the program is one of the ones that only ever read, whatever they are
      asked to do;
    - the program dispatches on a subcommand and was given one it does not
      have, so it fails at dispatch a second time exactly as it did the first.

    """
    words = _words(script)
    if words is None:
        return False
    if not words:
        # Assignments and nothing else, which a subshell throws away.
        return True

    program = words[0]
    name = os.path.basename(program)
    if name in EFFECTIVE_BUILTINS or program in EFFECTIVE_BUILTINS:
        return False
    if name in READ_ONLY:
        return True

    from .utils import which

    if which(program) is None:
        return True

    return _dispatch_fails(program, words[1:])


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
