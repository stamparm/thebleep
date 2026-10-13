# -*- encoding: utf-8 -*-

"""`cargo run --bin servr` -> `cargo run --bin server` from Cargo.toml."""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument_in_command


MISSING = re.compile(r'no bin target named [`\']([^`\'\r\n]+)')
# What cargo itself offers: `Did you mean `app`?` (1.85) and `help: a target
# with a similar name exists: `app`` (1.99). A default `cargo new` crate has
# no `[[bin]]` table for this to read, so cargo's word was the only answer.
SUGGESTED = re.compile(r'(?:Did you mean|a target with a similar name exists:)'
                       r' `([^`\r\n]+)`')


@for_app('cargo')
def match(command):
    return ('--bin' in command.script_parts
            and MISSING.search(command.output) is not None)


def get_new_command(command):
    broken = MISSING.search(command.output).group(1)
    candidates = SUGGESTED.findall(command.output)
    binaries = project_context.cargo_bins() or []
    candidates += [binary for binary in matching.rank(broken, binaries, limit=3)
                   if binary not in candidates]

    return [
        replace_argument_in_command(command, 'cargo', broken,
                                    shell.quote(binary))
        for binary in candidates]
