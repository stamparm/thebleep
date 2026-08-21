import os
import shlex
from subprocess import Popen, PIPE, STDOUT, TimeoutExpired
from .. import logs
from ..conf import settings
from ..utils import Tail, drain


def _kill_process(proc):
    """Tries to kill the process otherwise just logs a debug message, the
    process will be killed when thebleep terminates.

    :type proc: Process

    """
    from psutil import AccessDenied, NoSuchProcess

    try:
        proc.kill()
    except NoSuchProcess:
        # It exited between being listed and being killed, which is the
        # ordinary way a process tree comes apart under a timeout -- the work
        # is done, not failed. Catching only `AccessDenied` here turned a
        # timeout into a traceback whenever the race went this way.
        return
    except AccessDenied:
        try:
            executable = proc.exe()
        except Exception:                                    # noqa: BLE001
            executable = 'unknown executable'

        logs.debug(u'Rerun: process PID {} ({}) could not be terminated'.format(
            proc.pid, executable))


def _kill_tree(popen):
    """Kills the command and anything it started."""
    from psutil import Process

    try:
        proc = Process(popen.pid)
        children = proc.children(recursive=True)
    except Exception:                                        # noqa: BLE001
        # No tree to walk -- it has already gone, or this system will not say.
        # `Popen.kill` on a pid that has exited is a no-op, so this is safe
        # either way.
        try:
            popen.kill()
        except Exception:                                    # noqa: BLE001
            pass
        return

    for child in children:
        _kill_process(child)
    _kill_process(proc)


# How much of a command's output is kept. `communicate()` returns everything the
# command printed, and `settings.wait_command` bounds the *time* it has to print
# it, not the number of bytes -- a failed build or a test suite in a loop can
# put hundreds of megabytes through a pipe in three seconds, and all of it was
# being accumulated in memory and then decoded into a second copy. A rule reads
# an error message, so what is kept is the end of the output; the recording
# reader has always worked to a fixed size for the same reason.
MAX_OUTPUT = 8 * 1024 * 1024


def _wait_output(popen, is_slow):
    """Returns the command's output, or `None` if it ran out of time.

    The output is read while the command runs rather than after it exits. A
    command that writes more than fits in the pipe buffer blocks until someone
    reads it, so waiting for it to finish first is a deadlock: it used to mean
    anything printing more than about 64KB — a failed build, a noisy test run —
    hit the timeout and produced no output at all, leaving nothing to correct
    from.

    The reading is done by a thread rather than by `communicate`, which is what
    puts a ceiling on how much is held: `communicate` hands back every byte the
    command printed, and there is no way to ask it for less.

    :type popen: Popen
    :rtype: bytes | None

    """
    import threading

    timeout = settings.wait_slow_command if is_slow else settings.wait_command

    # `communicate` used to do this: an unclosed stdin is a command that waits
    # for input nobody is going to send, until the timeout.
    if popen.stdin is not None:
        try:
            popen.stdin.close()
        except Exception:                                    # noqa: BLE001
            pass

    sink = Tail(MAX_OUTPUT)
    reader = threading.Thread(target=drain, args=(popen.stdout, sink))
    reader.daemon = True
    reader.start()

    try:
        popen.wait(timeout=timeout)
    except TimeoutExpired:
        _kill_tree(popen)
        try:
            popen.wait(timeout=1)
        except Exception:                                    # noqa: BLE001
            pass
        return None

    # The command has exited; anything still in the pipe arrives now. A
    # grandchild that inherited the pipe and outlived its parent can hold it
    # open, so this waits a moment rather than forever and settles for what
    # arrived -- `communicate` would have blocked there indefinitely.
    reader.join(1)
    if sink.truncated:
        logs.debug(u'Rerun: kept the last {} bytes of the output'.format(
            MAX_OUTPUT))
    return sink.value()


# What the shell alias sets on its way in to hand us the shell's own state.
# None of it was in the environment when the command originally ran, and
# `TB_SHELL_ALIASES` and `TB_HISTORY` hold the user's aliases and their last ten
# commands -- so a command being run a second time to read its output must not
# inherit any of it.
#
# By name, and not by `TB_` prefix as this once did. `TB_` is short and generic
# enough to belong to somebody else -- a build system, an in-house tool, a
# company's own convention -- and deleting a stranger's variable makes the
# command behave differently the second time for a reason nobody could find.
# Adding a name to the transport means adding it here, which is a line in the
# same commit.
TRANSPORT = frozenset((
    'TB_ALIAS', 'TB_CAN_EDIT', 'TB_CMD', 'TB_EDIT', 'TB_EXIT', 'TB_HISTORY',
    'TB_OVERRIDDEN_ALIASES', 'TB_PROMPT', 'TB_SHELL', 'TB_SHELL_ALIASES',
    'TB_STATUS',
))

# `GIT_TRACE=1` makes git report the alias it expanded, which is the only way
# to learn that `git st` meant `git status`; `specific.git.git_support` reads it
# out of the output. It is a debugging switch that other programs also read, so
# it goes to git and to nothing else.
GIT_ENV = {'GIT_TRACE': '1'}

GIT_APPS = ('git', 'hub')


def _child_environment(program):
    """The environment to run `program` in, as close to the original as we can.

    """
    env = {key: value for key, value in os.environ.items()
           if key not in TRANSPORT}

    # A settings file is Python, so `env` can be anything at all -- and
    # `env = None` in somebody's `settings.py` used to come back here as a
    # `TypeError` from the middle of a correction.
    if isinstance(settings.env, dict):
        env.update({str(key): str(value)
                    for key, value in settings.env.items()})
    elif settings.env is not None:
        logs.warn(u'The `env` setting should be a dict, not {}; ignoring it'
                  .format(type(settings.env).__name__))

    if program and os.path.basename(program) in GIT_APPS:
        env.update(GIT_ENV)
    return env


def _is_slow(words):
    """Whether `words` runs one of the commands allowed the longer timeout.

    Asked of the command itself rather than of the first word, which is not the
    same thing often enough to matter: `FOO=1 gradle test`, `sudo gradle test`
    and `/usr/bin/gradle test` all used to be handed the three-second timeout
    meant for something quick, so they timed out and produced nothing to correct
    from -- the exact case `slow_commands` exists for.

    """
    from ..utils import command_word_index
    from ..wrappers import wrapped_app

    # `FOO=1 gradle test`: the assignments are not the command.
    words = words[command_word_index(words):]
    if not words:
        return False

    program = wrapped_app(words) or words[0]
    return (program in settings.slow_commands
            or os.path.basename(program) in settings.slow_commands)


def _call(expanded):
    """`(argv, shell)` for running `expanded` again, in the right shell.

    `Popen(expanded, shell=True)` runs through the *platform's* default shell,
    which on POSIX is `/bin/sh` -- whatever shell the command actually failed
    in. So a bash-ism came back as an `sh` error, and The Bleep corrected a
    problem the user never had:

        $ [[ -f /nope ]]                # bash: exits 1, prints nothing
        $ bleep
        /bin/sh: 1: [[: not found       # a different error entirely

    Each shell says how to run one of its own command lines; see
    `shells.Generic.replay_argv`. A shell that will not say, or a shell nothing
    here recognises, falls back to what this always did.

    """
    from ..shells import shell
    from ..utils import which

    try:
        argv = shell.replay_argv(expanded)
    except Exception:                                        # noqa: BLE001
        argv = None

    # And the interpreter has to be there. `TB_SHELL` says which shell the
    # command was typed in, not that this machine can start another one of it:
    # a Windows runner with `TB_SHELL=bash` and no bash on `PATH` got a `Popen`
    # that raised, so the correction had no output at all and answered
    # `No bleeps given` -- worse than the wrong shell, which at least printed
    # something a rule could read.
    if argv and which(argv[0]):
        return argv, False

    return expanded, True


def get_output(script, expanded):
    """Runs the script and obtains stdin/stderr.

    :type script: str
    :type expanded: str
    :rtype: str | None

    """
    try:
        split_expand = shlex.split(expanded)
    except ValueError:
        # An unbalanced quote is the sort of thing people ask to have fixed, so
        # it cannot be a crash. It only decides whether this counts as one of
        # the slow commands, and an unparseable one does not.
        split_expand = []

    from ..utils import command_word_index

    words = split_expand[command_word_index(split_expand):]
    program = words[0] if words else None
    env = _child_environment(program)

    # The rest of the environment is none of the log's business, and neither are
    # the *values* of what is left: `env` in a settings file is where people put
    # tokens, and the issue template asks for debug output to be pasted into a
    # bug report. Names only.
    logged_env = sorted(key for key in env
                        if key in GIT_ENV
                        or (isinstance(settings.env, dict)
                            and key in settings.env))

    is_slow = _is_slow(split_expand)
    with logs.debug_time(u'Call: {}; with env: {}; is slow: {}'.format(
            script, logged_env, is_slow)):
        argv, through_a_shell = _call(expanded)
        result = Popen(argv, shell=through_a_shell, stdin=PIPE,
                       stdout=PIPE, stderr=STDOUT, env=env)
        output = _wait_output(result, is_slow)
        if output is None:
            logs.debug(u'Execution timed out!')
            return None

        output = output.decode('utf-8', errors='replace')
        if settings.debug:
            # Formatting this is not free when the command printed a megabyte.
            logs.debug(u'Received output: {}'.format(output))
        return output
