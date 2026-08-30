# -*- encoding: utf-8 -*-

"""`make buld` -> `make build`, using the project's declared targets.

GNU make says:

    make: *** No rule to make target 'buld'.  Stop.

The nearest Makefile is a stronger source of candidates than a system-wide
word list.  Only static target names are read, and an uncertain or dynamic
Makefile produces no suggestion.
"""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument_in_command


MISSING = re.compile(r"No rule to make target ['\"]([^'\"]+)['\"]")


@for_app('make')
def match(command):
    return ('No rule to make target' in command.output
            and MISSING.search(command.output) is not None)


def get_new_command(command):
    broken = MISSING.search(command.output).group(1)
    targets = project_context.make_targets()
    if not targets:
        return []

    return [
        replace_argument_in_command(command, 'make', broken,
                                    shell.quote(target))
        for target in matching.rank(broken, targets, limit=3)]
