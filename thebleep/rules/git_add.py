# -*- encoding: utf-8 -*-

"""A file that is there but that git has never been told about.

    $ git checkout notes.md
    error: pathspec 'notes.md' did not match any file(s) known to git
    $ bleep
    git add -- 'notes.md' && git checkout notes.md

The file existing on disk is what separates this from a typo: a name git does
not know *and* cannot find is somebody else's problem -- `git_checkout` looks
for a branch that resembles it -- while a name git does not know and that is
sitting right there has one obvious explanation.

The message used to be matched with a full stop on the end, and git dropped it:
2.43 prints `... known to git` and nothing more. So the rule had been dead since
whichever version made that change, and its sibling `git_checkout` -- which
matches the same message without the full stop -- had been answering alone.

`git add` has a wording of its own, `fatal: pathspec 'x' did not match any
files`, and it is matched too. It cannot fire from a plain `git add` (a file
that exists is a file `git add` would have added) but `git add -u`, `git stash
push` and `git rm` all print it about a path they will not touch.

Wordings captured from git 2.43.

"""

import re
from thebleep.shells import shell
from thebleep.specific.git import git_support
from thebleep.system import Path
from thebleep.utils import memoize

# Two wordings, and neither ends in a full stop any more.
PATHSPEC = re.compile(r"pathspec '([^']*)' "
                      r'did not match any file(?:\(s\) known to git|s)')


@memoize
def _get_missing_file(command):
    found = PATHSPEC.search(command.output)
    if not found:
        return None

    pathspec = found.group(1)
    if Path(pathspec).exists():
        return pathspec


@git_support
def match(command):
    return bool(_get_missing_file(command))


@git_support
def get_new_command(command):
    missing_file = _get_missing_file(command)
    return shell.and_(u'git add -- {}'.format(shell.quote(missing_file)),
                      command.script)
