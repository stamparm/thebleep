# -*- encoding: utf-8 -*-

"""`cp a.txt no/such/dir/a.txt` -> make the directory first, then copy.

The same case as `cp_create_destination`, and this was the weaker copy of it:

- `file[0:file.rfind('/')]` on a destination with no `/` in it is `''`, so
  `mv a.txt b.txt` in a directory that had just been removed under the shell
  produced `mkdir -p  && mv a.txt b.txt` -- `mkdir` with no argument, which
  fails with its own usage message.
- it matched `Not a directory` as well, which `cp x realfile/` prints when
  `realfile` is a file. `mkdir -p realfile` then fails too.
- it had no busybox wording and no `mv ... to ...` capture that distinguishes a
  missing *destination* from a missing *source*.

So the regexes and the reasoning live in one place now, and this defers to it.
The rule stays because it is enabled separately and somebody's settings name it.

"""

import os
from thebleep.rules.cp_create_destination import _destination
from thebleep.shells import shell


def match(command):
    return _destination(command.output) is not None


def get_new_command(command):
    destination = _destination(command.output)

    directory = (destination.rstrip('/') if destination.endswith('/')
                 else os.path.dirname(destination))
    if not directory:
        # A bare filename: there is no parent directory to make, so there is
        # nothing to suggest. `mkdir -p ''` is not it.
        return []

    return shell.and_(shell.mkdir_p(directory), command.script)
