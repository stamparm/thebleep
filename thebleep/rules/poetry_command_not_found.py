# -*- encoding: utf-8 -*-

"""`poetry run servr` -> `poetry run server` from pyproject.toml."""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument_in_command


MISSING = re.compile(r'Command not found:\s*([^\s\r\n]+)', re.IGNORECASE)


@for_app('poetry')
def match(command):
    return ('run' in command.script_parts
            and MISSING.search(command.output) is not None)


def get_new_command(command):
    broken = MISSING.search(command.output).group(1)
    scripts = project_context.poetry_scripts()
    if not scripts:
        return []

    return [
        replace_argument_in_command(command, 'poetry', broken,
                                    shell.quote(script))
        for script in matching.rank(broken, scripts, limit=3)]
