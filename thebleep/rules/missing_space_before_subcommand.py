from thebleep.shells import shell
from thebleep.utils import get_all_executables, memoize


@memoize
def _executables():
    """Everything runnable, as a set.

    This rule has no app name and no output marker, so it is consulted for
    every failed command there is -- and it asked `word in
    get_all_executables()`, which is a scan of a list of some thousands of
    names, before scanning the same list again to find one the word starts
    with.

    """
    return set(get_all_executables())


@memoize
def _get_executable(script_part):
    for executable in get_all_executables():
        if len(executable) > 1 and script_part.startswith(executable):
            return executable


def _is_a_command_already(word):
    """Whether the shell would find something to run under this name.

    Both halves matter. `get_all_executables` is what is on `PATH` plus your
    aliases, and it does not include the shell's own builtins -- so `command`,
    `time` and `builtin` looked like words nobody could run, and this rule
    helpfully offered to break `command git status` into `comm and git status`.

    """
    return (word in _executables()
            or word in shell.get_builtin_commands())


def match(command):
    return (command.script_parts
            and not _is_a_command_already(command.script_parts[0])
            and _get_executable(command.script_parts[0]))


def get_new_command(command):
    executable = _get_executable(command.script_parts[0])
    return command.script.replace(executable, u'{} '.format(executable), 1)


priority = 4000


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
