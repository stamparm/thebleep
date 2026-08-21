# -*- encoding: utf-8 -*-

"""`pip instatl requests` -> `pip install requests`, from pip's own guess.

    $ pip instatl requests
    ERROR: unknown command "instatl" - maybe you meant "install"

pip names exactly one candidate, and taking it on trust is fine when the
candidate is `install`. It is not fine here:

    $ pip nistall requests
    ERROR: unknown command "nistall" - maybe you meant "uninstall"

The only suggestion offered was `pip uninstall requests`, arrowing down never
reached another, and pressing enter removed the package -- the opposite of what
was typed. Only pip's own confirmation prompt stood in the way, and `-y` removes
that.

`difflib` cannot fix this, which is why the first version of it here did not
try: it scores `nistall` against `uninstall` at 0.875 and against `install` at
0.857, so sorting keeps the wrong answer in front. That version measured the
*margin* between those two ratios and demoted a destructive candidate on a near
tie -- it worked, and it was the wrong layer. Counting how someone mistypes
instead makes the whole thing fall out:

    typo        install   uninstall
    nistall     1 edit    2 edits    <- a transposition of `install`
    instal      1 edit    2 edits
    isntall     1 edit    2 edits
    unistall    2 edits   1 edit     <- and this really does mean `uninstall`
    uninstal    2 edits   1 edit

No margin, no list of which subcommands are dangerous, no tuning constant.
Both directions come out right because the measure finally matches the mistake.
See `thebleep.matching`.

"""

import re
from thebleep import matching
from thebleep.utils import for_app, memoize, replace_argument
from thebleep.specific.sudo import sudo_support

BROKEN = re.compile(r'unknown command "([^"]+)"')
MEANT = re.compile(r'maybe you meant "([^"]+)"')


@memoize
def _pip_commands(interpreter):
    """Every subcommand this pip has, asked of this pip.

    Read from the same table pip dispatches on, so it is the list and not a
    document about one: `pip/_internal/cli/main_parser.py` builds the help from
    `commands_dict` and then dispatches on `commands_dict`. Anything other than
    a clean answer is an empty list, and then pip's own guess is all there is,
    which is where this started.

    """
    from thebleep.utils import tool_output

    source = ('import sys;'
              'from pip._internal.commands import commands_dict;'
              'sys.stdout.write("\\n".join(commands_dict))')
    # Ten seconds rather than the usual five: this starts an interpreter and
    # imports pip, which on a cold page cache is not quick.
    return tool_output((interpreter, '-c', source), timeout=10).split()


def _interpreter(command):
    """The `python` that goes with the `pip` that was run.

    `pip` is a console script whose shebang names its own interpreter, and that
    is the one to ask -- a machine may have several pips and they need not agree
    on what subcommands exist.

    """
    from thebleep.utils import which

    path = which(command.script_parts[0])
    if path is None:
        return None

    try:
        with open(path, 'rb') as handle:
            first = handle.readline(4096)
    except OSError:
        return None

    if not first.startswith(b'#!'):
        return None

    words = first[2:].strip().decode('utf-8', 'replace').split()
    return words[0] if words else None


def _ordered(broken, guess, others):
    """Candidates by how near they are to what was typed, best first.

    pip's own guess is kept whatever the measure makes of it -- it came out of
    pip's matcher rather than ours -- but it no longer leads simply for having
    been pip's.

    """
    candidates = ([guess] if guess else [])
    candidates += [name for name in others if name != guess]

    from thebleep.conf import settings

    return matching.order(broken, candidates,
                          limit=settings.num_close_matches)


@sudo_support
@for_app('pip', 'pip2', 'pip3')
def match(command):
    # `for_app` has already established that this is pip.
    return ('unknown command' in command.output
            and 'maybe you meant' in command.output
            and bool(BROKEN.search(command.output)))


@sudo_support
def get_new_command(command):
    from thebleep.shells import shell

    broken = BROKEN.search(command.output).group(1)
    meant = MEANT.search(command.output)
    guess = meant.group(1) if meant else None

    interpreter = _interpreter(command)
    others = _pip_commands(interpreter) if interpreter else []

    # Quoted, as `replace_command` would: a subcommand name read out of output
    # goes back to a shell that evaluates it. `replace_command` is not called
    # because it still orders by `difflib`, which is what put `uninstall` in
    # front of `install`.
    return [replace_argument(command.script, broken, shell.quote(name))
            for name in _ordered(broken, guess, others)]
