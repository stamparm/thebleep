# -*- encoding: utf-8 -*-

"""`git help st` where `st` is an alias -- ask about what it stands for.

    $ git help st
    'st' is aliased to 'status'
    $ bleep
    git help status

The quoting is the whole story here. git once wrote this line with backticks,
`` `git st' is aliased to `status' ``, and the rule read the name by splitting on
the backtick and taking the third piece. Current git uses ordinary quotes and
there is no third piece, so the split raised `IndexError` -- which means this
did not merely stop working, it printed a traceback into the terminal of anybody
who ran `git help <alias>`. Verified against git 2.30.2, 2.39.5 and 2.47.3, all
three of which print quotes.

"""

import re
from thebleep.shells import shell
from thebleep.specific.git import git_support

# Either quoting, and only the first word of what it stands for: an alias may
# expand to a whole command line (`st = status --short --branch`) and only the
# subcommand is a thing `git help` can be asked about.
ALIASED = re.compile(r"""is aliased to ['`"]?([^\s'`"]+)""")


@git_support
def match(command):
    return ('help' in command.script_parts
            and ' is aliased to ' in command.output
            and bool(ALIASED.search(command.output)))


@git_support
def get_new_command(command):
    # The alias comes out of `.git/config`, so a repository you cloned chose it.
    aliased = ALIASED.search(command.output).group(1)
    return 'git help {}'.format(shell.quote(aliased))
