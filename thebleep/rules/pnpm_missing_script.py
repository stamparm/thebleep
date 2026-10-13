# -*- encoding: utf-8 -*-

"""`pnpm run buld` -> `pnpm run build` from package.json."""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument_in_command


# pnpm 9 and 10 print ` ERR_PNPM_NO_SCRIPT  Missing script: buld`, pnpm 11
# `[ERR_PNPM_NO_SCRIPT] Missing script: buld`, and pnpm 12
#
#     Error: ERR_PNPM_NO_SCRIPT
#
#       × Missing script: buld
#
# This read only the bracketed form, so it fired on pnpm 11 alone. Captured
# from 9.15.9, 10.34.7, 11.28.5 and 12.11.2.
NO_SCRIPT = re.compile(
    r'ERR_PNPM_NO_SCRIPT\]?[\s\u00d7]{1,12}Missing script:\s*([^\s\r\n]+)')
NO_COMMAND = re.compile(
    r'ERR_PNPM_RECURSIVE_EXEC_FIRST_FAIL\]?[\s\u00d7]{1,12}'
    r'Command "([^"\r\n]+)"\s+not found')
SUGGESTED = re.compile(r'Did you mean "pnpm(?: run)? ([^"\r\n]+)"')


# pnpm's own commands, from `pnpm --help` (pnpm 10).
COMMANDS = ('add', 'install', 'remove', 'update', 'run', 'exec', 'dlx',
            'test', 'start', 'init', 'list', 'outdated', 'audit', 'why',
            'publish', 'link', 'unlink', 'store', 'prune', 'rebuild', 'pack',
            'create', 'import', 'patch', 'deploy', 'config', 'licenses')


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
    if NO_COMMAND.search(command.output):
        # `pnpm instal` is not a script typo but one of pnpm's own commands,
        # and pnpm names nothing for it.
        candidates += [name for name in matching.rank(broken, COMMANDS, limit=3)
                       if name not in candidates]

    return [
        replace_argument_in_command(command, 'pnpm', broken,
                                    shell.quote(candidate))
        for candidate in candidates]
