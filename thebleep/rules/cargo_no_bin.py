# -*- encoding: utf-8 -*-

"""`cargo run --bin servr` -> `cargo run --bin server` from Cargo.toml."""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument


MISSING = re.compile(r'no bin target named [`\']([^`\'\r\n]+)')


@for_app('cargo')
def match(command):
    return ('--bin' in command.script_parts
            and MISSING.search(command.output) is not None)


def get_new_command(command):
    broken = MISSING.search(command.output).group(1)
    binaries = project_context.cargo_bins()
    if not binaries:
        return []

    return [replace_argument(command.script, broken, shell.quote(binary))
            for binary in matching.rank(broken, binaries, limit=3)]
