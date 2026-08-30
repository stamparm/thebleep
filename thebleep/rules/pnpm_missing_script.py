# -*- encoding: utf-8 -*-

"""`pnpm run buld` -> `pnpm run build` from package.json."""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument_in_command


NO_SCRIPT = re.compile(
    r'\[ERR_PNPM_NO_SCRIPT\]\s+Missing script:\s*([^\s\r\n]+)')
NO_COMMAND = re.compile(
    r'\[ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL\]\s+Command "([^"\r\n]+)"'
    r'\s+not found')
SUGGESTED = re.compile(r'Did you mean "pnpm(?: run)? ([^"\r\n]+)"')


@for_app('pnpm')
def match(command):
    return NO_SCRIPT.search(command.output) or NO_COMMAND.search(command.output)


def get_new_command(command):
    missing = NO_SCRIPT.search(command.output) or NO_COMMAND.search(
        command.output)
    broken = missing.group(1)

    suggested = SUGGESTED.findall(command.output)
    candidates = matching.order(broken, suggested, limit=3)
    scripts = project_context.package_scripts()
    if scripts is not None:
        candidates += [name for name in matching.rank(broken, scripts, limit=3)
                       if name not in candidates]

    return [
        replace_argument_in_command(command, 'pnpm', broken,
                                    shell.quote(candidate))
        for candidate in candidates]
