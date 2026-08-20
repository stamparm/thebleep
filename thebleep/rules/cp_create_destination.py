# -*- encoding: utf-8 -*-

"""`cp a.txt no/such/dir/a.txt` -> make the directory first, then copy.

Two things were wrong, and the first one produced a wrong result that looked
like a right one:

    $ cp a.txt nosuchdir/a.txt
    cp: cannot create regular file 'nosuchdir/a.txt': No such file or directory
    $ bleep
    mkdir -p nosuchdir/a.txt && cp a.txt nosuchdir/a.txt     <- accepted
    $ ls -lR nosuchdir
    nosuchdir:
    drwxr-xr-x 2 root root 4096 nosuchdir/a.txt              <- a *directory*
    nosuchdir/a.txt:
    -rw-r--r-- 1 root root    4 a.txt

The destination was `mkdir`ed whole, filename included, so the copy went
*inside* a directory named after the file it should have been. The command
exited 0 and said nothing, so there was no reason to look.

Second, the rule fired on `No such file or directory` however it arose,
including when the missing thing was the *source*:

    $ mv typoo.txt newname.txt
    mv: cannot stat 'typoo.txt': No such file or directory
    $ bleep
    mkdir -p newname.txt && mv typoo.txt newname.txt         <- fails, and
                                                                leaves a
                                                                directory behind

Both are fixed by reading which path the message names. `cannot create` and
`cannot move ... to` name the destination, which is the case this rule is for;
`cannot stat` names the source, which is somebody else's. Wordings captured from
GNU coreutils 9.x.

"""

import os
import re
from thebleep.shells import shell
from thebleep.utils import for_app

# The destination could not be made, and the message names it -- which is what
# to act on, rather than whichever word happened to come last on the command
# line. Captured from GNU coreutils 9.x and from busybox 1.37.
#
# busybox `mv` is deliberately absent. It prints `mv: can't rename 'a.txt': No
# such file or directory` and prints exactly that whether the missing thing is
# the source or the destination, so there is no way to tell the two apart and no
# destination to make. Guessing there is how the source-missing case came to be
# treated as a destination in the first place.
#
# So is `cp: cannot create regular file 'nodir/': Not a directory`, which GNU
# prints for a trailing slash that does not exist. It looks like this rule's
# case, but the same message comes out of `cp x realfile/` where `realfile` is a
# file -- and `mkdir -p realfile` then fails.
DESTINATION = (
    # GNU cp.
    re.compile(r"cannot create (?:regular file|directory|symbolic link) "
               r"'([^']+)': No such file or directory"),
    # GNU mv.
    re.compile(r"cannot move '[^']*' to '([^']+)': No such file or directory"),
    # busybox cp.
    re.compile(r"can't create '([^']+)': No such file or directory"),
)


def _destination(output):
    for pattern in DESTINATION:
        found = pattern.search(output)
        if found:
            return found.group(1)

    return None


@for_app('cp', 'mv')
def match(command):
    return _destination(command.output) is not None


def get_new_command(command):
    destination = _destination(command.output)

    # The directory to make is the one holding the destination, not the
    # destination itself. A destination that names a directory outright -- a
    # trailing separator -- is its own answer.
    directory = (destination.rstrip('/') if destination.endswith('/')
                 else os.path.dirname(destination))

    return shell.and_(shell.mkdir_p(directory), command.script)
