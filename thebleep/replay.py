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
it a second time exactly as it did the first. The shell says as much in the exit
status -- 127 for a command it could not find, 126 for one it could not run --
and that covers an alias or a function or a `PATH` that has changed underneath,
which a name lookup does not.

The other side of the same coin: a command that **succeeded** has nothing to
correct. Re-running it can only repeat whatever it did, and the correction it
produces is a correction to a problem the re-run created. `git tag v9` succeeds
silently; running it again says `already exists`; the suggestion was
`git tag --force v9`, offered for output the user never saw and moving a tag
that was already right. So a successful command is not re-run -- and not asked
about either, since there is nothing to gain by asking.

That last rule applies only where a question was going to be asked. `ls` that
printed nothing is inert whatever it exited with, so `ls` is still re-read and
still offered `ls -A`.

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
#   xxd    takes an output file as its second operand, and `-r` patches a file
#          in place -- `xxd -r patch.hex target` is what its own manual page
#          demonstrates. It was on this list until somebody read the manual.
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
    'whoami', 'zcat', 'zgrep',
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
# `nohelpers` is *not* asked for, though it looks tidier: it subtracts the eight
# `--`-suffixed commands -- `web--browse`, `submodule--helper`,
# `credential-cache--daemon` and the rest -- and every one of them dispatches.
# With them filtered out, `git web--browse http://x` looked like a typo and its
# browser was launched a second time without a question.
#
# The bar for being here is that the answer is *complete*: every word the
# program will dispatch on has to be in it, because one that is missing looks
# like a typo and its command then runs again unasked. Over-inclusion is
# harmless -- a word taken for a subcommand it is not merely asks -- which is
# why the answer is read as a bag of words rather than parsed. Under-inclusion
# is the whole risk, and it is not a theoretical one:
#
#   npm     `uninstal` is in neither `npm help` nor `npm -l`, dispatches, and
#           takes the dependency out of your `package.json`. npm matches on any
#           unambiguous abbreviation of a command or alias, so its dispatch set
#           is far larger than anything it prints.
#   uv      `uv build-backend` is absent from both `uv --help` and `uv help`,
#           and runs.
#   docker  the sharpest one, because the listing looks complete and is not: a
#           CLI plugin is printed as `compose*`, with the asterisk. Split into
#           words that gives `compose*`, so the word that actually dispatches --
#           `compose` -- is missing, and `docker compose up -d` would have been
#           taken for a typo and run again. A `--help` screen is a document laid
#           out for a person, not a promise about what the program accepts.
#   apt-get `full-upgrade`, `auto-remove` and `auto-clean` dispatch and are
#           absent; the help calls itself "Most used commands" and points at the
#           manual page, which is the program declining to claim completeness.
#   yarn    no listing can ever be complete: an unrecognised word is looked up
#           as a script in the local `package.json`, so the dispatch set is
#           whatever the current directory says it is.
#
# `kubectl` is the closest near miss -- its `--help` even lists plugins -- but
# `kubectl alpha` dispatches and is absent, so it fails the same bar.
DISPATCHERS = {
    'git': ('--list-cmds=main,others,alias',),
    'cargo': ('--list',),
}

# Long enough for a program to print a list it already knows, short enough that
# nobody waits on it. Whatever does not answer in the time is treated as not
# having answered, which asks.
PROBE_TIMEOUT = 5


def _words(script):
    """The words `sh` would run, or `None` if it isn't that simple.

    The script is the expanded one, so a shell alias has already been resolved
    into whatever it stands for.

    An empty list means assignments and nothing else, which a subshell throws
    away. A leading assignment in front of a *command* makes this return `None`:
    see `_assignments_change_everything`.

    """
    if any(syntax in script for syntax in EFFECTIVE_SYNTAX):
        return None

    words = script.split()
    if not words:
        return None

    # `FOO=bar cmd` sets FOO for cmd; the assignments are not the command.
    from .utils import command_word_index

    at = command_word_index(words)
    words = words[at:]
    if not words:
        # Assignments and nothing else. A subshell throws those away, and there
        # is no command for them to change the meaning of.
        return []

    if at and _assignments_change_everything():
        return None

    if not LITERAL_PROGRAM.match(words[0]):
        return None

    return words


def _assignments_change_everything():
    """Always true, and here to be read rather than to be called usefully.

    `FOO=bar cmd` is one command with an environment of its own, and every
    question this module asks about `cmd` is a question whose answer that
    environment can change. Two demonstrations, both reproduced:

        $ PATH=/tmp/mine:/usr/bin git satus
        $ bleep

    `_words` dropped the assignment to find the program, so the dispatcher probe
    asked `/usr/bin/git` whether it has a `satus`. It has not -- and the command
    that ran was `/tmp/mine/git`, which is a different program with different
    subcommands and a side effect. The proof was about one binary and the
    consent it bought was for another.

        $ GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.deploy \
              GIT_CONFIG_VALUE_0='!./deploy.sh' git deploy
        $ bleep

    Same shape without swapping anything: with those three variables set, `git
    --list-cmds=main,others,alias` lists `deploy`; without them it does not. The
    probe runs without them, calls `deploy` an unknown subcommand, and the alias
    it had already run does whatever it likes.

    The alternative to refusing is a list of the variables that can change how a
    program resolves or behaves -- `PATH`, `LD_PRELOAD`, `LD_LIBRARY_PATH`,
    `PYTHONPATH`, `GIT_CONFIG_*`, `BASH_ENV`, and whatever the next one is. That
    is exactly the sort of supposedly-complete security list this module refuses
    to keep elsewhere: `READ_ONLY` is a list of things believed *safe*, which
    fails towards asking, while a list of dangerous variables fails towards not
    asking.

    So an assignment in front of a command costs a question. `LC_ALL=C ls` is
    the common case and it is a keystroke.

    """
    return True


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


# What the shell said about the command before this one, or `None` when the
# shell did not say. Set by the alias, first thing, before anything else can
# clobber `$?`. Older aliases -- somebody's `.bashrc` from a previous release --
# do not set it, and then this is `None` and nothing below changes.
EXIT_ENV = 'TB_EXIT'

# There used to be a shortcut here: exit status 126 or 127 meant `command not
# found` or `cannot execute`, so nothing had run and the command could be run
# again without asking. It was wrong, and dangerously so. Those statuses are a
# *convention* the shell follows for its own failures -- nothing stops a program
# from exiting with either, and plenty do it on purpose:
#
#     $ make install            # a recipe's command was missing, four recipes
#     make: cc: No such file    # already having run
#     make: *** [install] Error 127
#     $ bleep
#     make install              # run again, unasked
#
# `npm run`, `sh -c`, and any wrapper that reports its child's status do the
# same. `previous_status() == 127` says only that *something* could not be
# found, not that nothing happened -- and the difference between those two is
# the whole question this module exists to answer. The `PATH` lookup below is
# the sound version of the same idea, and it stands on its own.


def previous_status():
    """What the previous command exited with, or `None` if unknown."""
    raw = os.environ.get(EXIT_ENV)
    if not raw:
        return None

    try:
        return int(raw)
    except ValueError:
        return None


# What bash calls an exported function in the environment. 4.3 and later use
# `BASH_FUNC_name%%`; older ones used the bare name with a body that starts
# `() {`, which is the shape Shellshock was about.
_EXPORTED_FUNCTION = 'BASH_FUNC_{}%%'


def _is_an_exported_function(name):
    """Whether `name` is a shell function the replay would inherit.

    The replay runs `bash -c <script>` in the shell the command was typed in,
    and bash imports exported functions from its environment -- so "not on
    `PATH`" stopped meaning "there is nothing to run":

        deploy() { printf x >> log; return 1; }
        export -f deploy

        $ deploy
        $ bleep          # which('deploy') is None, so this used to be free
        # ...and the function ran a second time, unasked.

    Reproduced end to end. The function is deliberately *not* stripped from the
    replay environment: the interactive shell had it, so running it is what
    faithfully reproduces the failure -- it just has to be asked about first.

    zsh does not export functions through the environment and fish has no
    equivalent, so this is bash's alone; a shell that grows one will need a
    line here.

    """
    return (_EXPORTED_FUNCTION.format(name) in os.environ
            # The pre-4.3 spelling, and belt-and-braces against a bash built to
            # use it: a variable whose name is the command and whose value is a
            # function body.
            or os.environ.get(name, '').startswith('() {'))


# Files a non-interactive shell runs before it runs anything it was asked to.
# `BASH_ENV` is bash's, `ENV` is POSIX `sh`'s and zsh reads it too.
STARTUP_FILE_ENV = ('BASH_ENV', 'ENV')


def _starting_the_shell_has_an_effect():
    """Whether merely opening the replay shell does something.

    A non-interactive bash sources whatever `BASH_ENV` names, before the command
    it was given. So with that set, replaying a command that does not exist at
    all still has an effect:

        $ BASH_ENV=/tmp/x bash -c nosuchcommand
        # /tmp/x ran

    Reproduced. This is the hole with the sharpest edge, because `is_inert` is a
    claim about the *command* while the replay executes a shell, its startup
    files, an inherited environment and then the command. The claim and the
    thing done have to be about the same object.

    Not stripped from the replay environment, though stripping would also close
    it: the variable is the user's, and a tool that quietly unsets part of
    somebody's environment to make its own proof come out true is worse than a
    tool that asks. It costs a question, in a configuration almost nobody has.

    """
    return any(os.environ.get(name) for name in STARTUP_FILE_ENV)


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
    if _starting_the_shell_has_an_effect():
        return False

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

    # `READ_ONLY` is a judgement about the program conventionally called `ls`,
    # and a path is not that. `./ls` is a file in this directory which the user
    # has specifically said to execute, and its name says nothing at all about
    # what it does -- one written for the occasion re-ran itself here and
    # doubled its side effect. A bare name at least goes through `PATH`, which
    # is the same lookup the shell just did.
    if program == name and name in READ_ONLY:
        return True

    if _is_an_exported_function(name):
        # `bash -c` imports functions the shell exported into the environment,
        # so a name that is not on `PATH` can still run something. See the
        # function.
        return False

    from .utils import which

    if which(program) is None:
        return True

    return _dispatch_fails(program, words[1:])


def _ask(script):
    """Asks whether the command may run again. Only `y` means yes.

    `get_key` does not always return a string. Ctrl+C, Escape and the arrows
    come back as the sentinel objects in `const.KEY_MAPPING`, and `.lower()` on
    one of those raised `AttributeError` -- so pressing Ctrl+C at this prompt,
    which is the obvious way to say "no, leave it alone", answered with a
    traceback instead.

    The test for this mocked `get_key` and handed it the *string* `'\x03'`, so
    it agreed with a contract the real function does not have. It now uses the
    real values.

    """
    from .system import get_key

    logs.confirm_replay(script)
    key = get_key()
    # Anything that is not the letter `y` is a no, and a key that is not a
    # letter at all is certainly not `y`.
    answered_yes = isinstance(key, str) and key.lower() == 'y'
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

    # It worked. There is nothing to read that would help, and running it again
    # is how `git tag v9` came to be answered with `git tag --force v9` -- a
    # correction to an error the re-run had just caused. Asked after `is_inert`
    # on purpose: a command that cannot have an effect is still worth re-reading
    # whatever it exited with.
    if previous_status() == 0:
        logs.debug(u'Replay: {} succeeded, so there is nothing to correct'
                   .format(expanded))
        return False

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
