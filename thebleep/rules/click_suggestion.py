# -*- encoding: utf-8 -*-

"""`black --chekc .` -> `black --check .`, for any tool built with Click.

The third of the framework rules, after `clap_suggestion` and
`cobra_suggestion`. Click is what most Python command line tools are written
with, and it names the options it thought you meant:

    $ black --chekc .
    Usage: black [OPTIONS] SRC ...
    Try 'black --help' for help.

    Error: No such option '--chekc'. (Did you mean one of: '--check', '--code',
    '--help'?)

So `black`, `flask`, `mkdocs`, `dvc`, `sqlfluff` and the rest come free.

Click offers `--help` among its guesses, which is true but never what was meant
-- nobody types `--chekc` for `--help`. It is dropped unless it is the only
thing offered.

Captured from black 25.9.0 (Click 8.x).

"""

import re
from thebleep.types import Suggestion
from thebleep.utils import replace_command

# The option Click did not recognise, and the ones it put forward. Both are in
# one sentence, so both come out of one match.
NO_SUCH_OPTION = re.compile(
    r"[Nn]o such option:?\s*'?(?P<broken>-[^'\s.]+)'?"
    r"(?:.*?\(Did you mean (?:one of )?(?P<suggestions>[^)]+)\))?",
    re.DOTALL)

# Click writes `No such option '--x'` in Click 8 and `no such option: --x` in
# older ones -- the colon went away and the quotes arrived -- so the marker is
# the part they share and both spellings are accepted. Requiring the colon is
# what made this match nothing at all the first time.
MARKER = 'o such option'


def _read(output):
    found = NO_SUCH_OPTION.search(output)
    if not found:
        return None, []

    suggestions = re.findall(r"'([^']+)'", found.group('suggestions') or '')

    # `--help` is always a valid option and never the answer.
    without_help = [name for name in suggestions if name != '--help']
    return found.group('broken'), without_help or suggestions


def match(command):
    # One `return` of literal-and-rest, which is the shape `rulepack` can read.
    # Written out rather than referring to `MARKER`, and not split into an early
    # return, because the extractor follows neither -- and a rule with no output
    # clause is loaded for every correction, which is the cost this design
    # exists to avoid.
    return ('o such option' in command.output
            and all(_read(command.output)))


def get_new_command(command):
    broken, suggestions = _read(command.output)
    return [Suggestion(fixed, confidence=0.98, evidence=(
        'click named this replacement in the command error',))
        for fixed in replace_command(command, broken, suggestions)]
