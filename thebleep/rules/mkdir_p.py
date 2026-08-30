# -*- encoding: utf-8 -*-

"""`mkdir foo/bar/baz` -> `mkdir -p foo/bar/baz`.

Two things it used to get wrong, and the first produced a suggestion that
cannot run:

    $ mkdir -p /tmp/q && rmdir /tmp/q/nope
    rmdir: failed to remove '/tmp/q/nope': No such file or directory
    $ bleep
    mkdir -p -p /tmp/q && rmdir /tmp/q/nope

The `mkdir` in that command *worked*. What failed was the `rmdir` after it, and
`No such file or directory` is a message half the tools on the machine print --
so the rule saw a command with `mkdir` in it and a message it recognised, and
added a `-p` that was already there.

So: the message has to be `mkdir`'s own, and the flag is not added twice. GNU
`mkdir` says `mkdir: cannot create directory 'x': No such file or directory` and
Hadoop's says ``mkdir: `x': No such file or directory``; both name themselves
first, which is what makes them tellable from the rest of a pipeline.

"""

import re
from thebleep.shells import shell
from thebleep.specific.sudo import sudo_support
from thebleep.utils import is_app

# `-p`, however it was spelled. `mkdir -pv` counts too.
PARENTS = re.compile(r'(?:^|\s)(?:--parents\b|-[a-zA-Z]*p[a-zA-Z]*(?=\s|$))')

# A line that is mkdir's own complaint rather than something else's. Some
# runners execute the probe by absolute path, so current GNU coreutils prints
# `/usr/bin/mkdir: ...`; accept that prefix while staying anchored so
# `rmdir: ... No such file or directory` does not qualify.
COMPLAINT = re.compile(
    r'(?m)^\s*(?:[^\r\n]*[\\/])?mkdir:.*No such file or directory')


def _makes_directories(command):
    """Whether this is a directory being made at all.

    `'mkdir' in command.script` was not: it matched `echo mkdir`,
    `git mkdir-x` and `python mkdirs.py`, and offered each of them back
    unchanged as a correction.

    """
    if is_app(command, 'mkdir', at_least=1):
        return True

    # Hadoop's file system commands: `hdfs dfs -mkdir <path>`.
    return is_app(command, 'hdfs') and '-mkdir' in command.script_parts


@sudo_support
def match(command):
    return (_makes_directories(command)
            and COMPLAINT.search(command.output) is not None
            and PARENTS.search(command.script) is None)


@sudo_support
def get_new_command(command):
    return re.sub('\\bmkdir (.*)',
                  '{} \\1'.format(shell.mkdir_command()),
                  command.script)
