import os
import shlex
from subprocess import Popen, PIPE, STDOUT, TimeoutExpired
from .. import logs
from ..conf import settings


def _kill_process(proc):
    """Tries to kill the process otherwise just logs a debug message, the
    process will be killed when thebleep terminates.

    :type proc: Process

    """
    from psutil import AccessDenied

    try:
        proc.kill()
    except AccessDenied:
        try:
            executable = proc.exe()
        except AccessDenied:
            executable = 'unknown executable'

        logs.debug(u'Rerun: process PID {} ({}) could not be terminated'.format(
            proc.pid, executable))


def _kill_tree(popen):
    """Kills the command and anything it started."""
    from psutil import Process

    try:
        proc = Process(popen.pid)
    except Exception:
        popen.kill()
        return

    for child in proc.children(recursive=True):
        _kill_process(child)
    _kill_process(proc)


def _wait_output(popen, is_slow):
    """Returns the command's output, or `None` if it ran out of time.

    The output is read while the command runs rather than after it exits. A
    command that writes more than fits in the pipe buffer blocks until someone
    reads it, so waiting for it to finish first is a deadlock: it used to mean
    anything printing more than about 64KB — a failed build, a noisy test run —
    hit the timeout and produced no output at all, leaving nothing to correct
    from.

    :type popen: Popen
    :rtype: bytes | None

    """
    timeout = settings.wait_slow_command if is_slow else settings.wait_command
    try:
        return popen.communicate(timeout=timeout)[0]
    except TimeoutExpired:
        _kill_tree(popen)
        try:
            popen.communicate(timeout=1)
        except Exception:
            pass
        return None


# What the shell alias sets on its way in to hand us the shell's own state.
# None of it was in the environment when the command originally ran, and
# `TB_SHELL_ALIASES` and `TB_HISTORY` hold the user's aliases and their last ten
# commands -- so a command being run a second time to read its output must not
# inherit any of it. Matched by prefix rather than by name: a variable added to
# the transport later is scrubbed without anyone having to remember to add it
# here too.
TRANSPORT_PREFIX = 'TB_'

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
           if not key.startswith(TRANSPORT_PREFIX)}
    env.update(settings.env)
    if program and os.path.basename(program) in GIT_APPS:
        env.update(GIT_ENV)
    return env


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
    env = _child_environment(words[0] if words else None)

    # The rest of the environment is none of the log's business, it tends to
    # carry tokens and keys that end up pasted into bug reports.
    logged_env = {key: value for key, value in env.items()
                  if key in settings.env or key in GIT_ENV}

    is_slow = split_expand[0] in settings.slow_commands if split_expand else False
    with logs.debug_time(u'Call: {}; with env: {}; is slow: {}'.format(
            script, logged_env, is_slow)):
        result = Popen(expanded, shell=True, stdin=PIPE,
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
