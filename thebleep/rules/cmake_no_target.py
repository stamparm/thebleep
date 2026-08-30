# -*- encoding: utf-8 -*-

"""`cmake --build build --target buil` -> `... --target build`.

The generated build tool reports a missing target, while the nearest
CMakeLists.txt provides a project-local vocabulary. Only static target names
are read; CMake files are never executed.
"""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument


MISSING = re.compile(r"No rule to make target ['\"]([^'\"]+)['\"]")


@for_app('cmake')
def match(command):
    return ('--build' in command.script_parts
            and '--target' in command.script_parts
            and MISSING.search(command.output) is not None)


def get_new_command(command):
    broken = MISSING.search(command.output).group(1)
    targets = project_context.cmake_targets()
    if not targets:
        return []

    return [replace_argument(command.script, broken, shell.quote(target))
            for target in matching.rank(broken, targets, limit=3)]
