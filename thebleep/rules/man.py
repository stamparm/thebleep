import re
from thebleep.shells import shell
from thebleep.utils import for_app, which

# The manual sections a page is most often in the other one of: system calls and
# library functions.
SECTIONS = {'2': '3', '3': '2'}

# A section as an argument of its own, or glued to `-s` as `man -s3 read`.
SECTION = re.compile(r'^(-s)?([23])$')


def _runnable(name):
    """Whether typing `name` would run something -- program or builtin."""
    return bool(which(name)) or name in shell.get_builtin_commands()


@for_app('man', at_least=1)
def match(command):
    return True


def get_new_command(command):
    # A section is an argument of its own. Looking for the characters `2` and `3`
    # anywhere in the script, which is what this used to do, turned
    # `man python3` into `man python2` and `man ls3` into `man ls2`.
    parts = list(command.script_parts)

    for index, part in enumerate(parts[1:], 1):
        found = SECTION.match(part)
        if found:
            parts[index] = (found.group(1) or '') + SECTIONS[found.group(2)]
            return u' '.join(parts)

    # A copy: `parts` used to be `command.script_parts` itself, and inserting
    # into it left every rule consulted afterwards looking at a command whose
    # parts had had ' 2 ' spliced into them.
    last_arg = parts[-1]

    # `<name> --help` is only an answer if `<name>` is something you can run.
    # `man ls` has no page on a slim system and `ls --help` is a good answer
    # there; `man nosuchpage` was answered with `nosuchpage --help`, which is
    # not a command at all. A suggestion that cannot run is worse than none.
    #
    # Builtins count: `man read` has no page because `read` is the shell's own,
    # and `read --help` is exactly the right place to look.
    help_command = (u'{} --help'.format(shell.quote(last_arg))
                    if _runnable(last_arg) else None)

    # No manual page at all, so there is no other section to try.
    if command.output.strip() == u'No manual entry for ' + last_arg:
        return [help_command] if help_command else []

    sections = [u' '.join([parts[0], '3'] + parts[1:]),
                u' '.join([parts[0], '2'] + parts[1:])]
    return sections + [help_command] if help_command else sections
