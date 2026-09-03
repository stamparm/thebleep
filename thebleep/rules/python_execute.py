# -*- encoding: utf-8 -*-

"""`python foo` -> `python foo.py`, when the file was simply named without it.

Example:
> python foo
python: can't open file '/tmp/foo': [Errno 2] No such file or directory

The rule used to ask nothing about why the command failed, so *every* failing
`python ...` whose script did not end in `.py` got `.py` appended -- a
traceback from a missing import answered with `python -c 'import x'.py`, and
`python --version` on a machine without Python 2 answered with
`--version.py`. The one error this rule is about is python saying the file
is not there at all, so that is what is matched now.

Captured from CPython 3.12; the wording has been stable since Python 3.

"""
from thebleep.utils import for_app

# `can't open file '...'`: the whole of what this rule knows. A missing module,
# a syntax error or any other failure is not a filename that lost `.py`.
OPEN_FAILED = "can't open file"


import os  # noqa: E402
import re  # noqa: E402

from thebleep.utils import replace_argument  # noqa: E402

# `python: can't open file '/home/u/foo': [Errno 2] No such file or directory`
NAMED = re.compile(r"can't open file '([^']+)'")


@for_app('python', 'python3', 'python2', at_least=1)
def match(command):
    return OPEN_FAILED in command.output and _named(command) is not None


def _named(command):
    """The file python could not open, as it appears in the command."""
    found = NAMED.search(command.output)
    if not found or found.group(1).endswith('.py'):
        return None
    name = os.path.basename(found.group(1))
    return name if name in command.script_parts else None


def get_new_command(command):
    name = _named(command)
    return replace_argument(command.script, name, name + '.py')
