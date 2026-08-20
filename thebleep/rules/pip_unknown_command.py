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

Ordering by closeness does not fix it, which was the surprise: `difflib` scores
`nistall` against `uninstall` at 0.875 and against `install` at 0.857, so
sorting keeps the wrong answer in front. What the numbers do show is that every
*genuine* typo is decided by a wide margin and only the truly ambiguous one is
close, so the margin is the thing to read. Measured:

    typo        install   uninstall
    instal      0.9231    0.8000    <- install, by 0.123
    isntall     0.8571    0.7500    <- install, by 0.107
    nistall     0.8571    0.8750    <- uninstall, by 0.018   ambiguous
    unistall    0.8000    0.9412    <- uninstall, by 0.141
    uninstal    0.8000    0.9412    <- uninstall, by 0.141

So `pip unistall` still means `uninstall` and is left alone, and only in a near
tie does the reading that removes your packages give up first place.

"""

import re
from difflib import SequenceMatcher, get_close_matches
from thebleep.utils import for_app, memoize, replace_argument
from thebleep.specific.sudo import sudo_support

BROKEN = re.compile(r'unknown command "([^"]+)"')
MEANT = re.compile(r'maybe you meant "([^"]+)"')

# pip subcommands that take something away. `install` can overwrite a version,
# which is a change but a recoverable one; `uninstall` is the one whose result
# cannot be got back by running it again.
REMOVES = frozenset({'uninstall'})

# How close two readings have to be before the destructive one stops being the
# answer enter runs. Every genuine typo above is decided by more than twice
# this.
NEAR = 0.05


@memoize
def _pip_commands(interpreter):
    """Every subcommand this pip has, asked of this pip.

    Read from the same table pip dispatches on, so it is the list and not a
    document about one: `pip/_internal/cli/main_parser.py` builds the help from
    `commands_dict` and then dispatches on `commands_dict`. Anything other than
    a clean answer is an empty list, and then pip's own guess is all there is,
    which is where this started.

    """
    from subprocess import check_output
    from thebleep.utils import DEVNULL

    source = ('import sys;'
              'from pip._internal.commands import commands_dict;'
              'sys.stdout.write("\\n".join(commands_dict))')
    try:
        answer = check_output((interpreter, '-c', source), stderr=DEVNULL,
                              timeout=10)
    except Exception:
        return []

    return answer.decode('utf-8', 'replace').split()


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
    """Candidates by closeness, with a near-tied destructive one demoted.

    pip's own guess is never dropped, whatever `difflib` makes of it: it came
    out of pip's matcher rather than ours, and `get_close_matches` has a cutoff
    that would otherwise throw away the one answer this rule has always had.

    """
    candidates = ([guess] if guess else [])
    candidates += [name for name in others if name != guess]

    close = get_close_matches(broken, candidates,
                              n=max(len(candidates), 1), cutoff=0.1)
    if guess and guess not in close:
        close = [guess] + close

    if len(close) < 2 or close[0] not in REMOVES:
        return close

    def ratio(name):
        return SequenceMatcher(None, broken, name).ratio()

    for other in close[1:]:
        if other not in REMOVES and ratio(close[0]) - ratio(other) < NEAR:
            return [other] + [name for name in close if name != other]

    return close


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
    # goes back to a shell that evaluates it. The ordering is the reason this
    # does not simply call `replace_command` -- that sorts by closeness alone,
    # which is what puts `uninstall` in front of `install`.
    return [replace_argument(command.script, broken, shell.quote(name))
            for name in _ordered(broken, guess, others)]
