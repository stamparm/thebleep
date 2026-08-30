# -*- encoding: utf-8 -*-

"""`bun run buidl` -> `bun run build`, and `bun instal` -> `bun install`.

bun names the word it did not recognise, and stops there:

    $ bun run buidl
    error: Script not found "buidl"

    $ bun instal
    error: Script not found "instal"

Two things follow from that. It offers no suggestion of its own -- there is no
"did you mean" to read here, so the candidates have to come from somewhere else
-- and an unknown word is looked up as a script whether or not `run` was typed,
which is why `bun instal` is reported as a missing *script* rather than as an
unknown command. One message covers both mistakes and both need answering.

So the candidates depend on what was asked for. After `bun run` only a script
can be meant, and those are read out of the project's `package.json` -- the
file bun itself would have read, found by walking up from the current directory
the way bun does. Without `run`, bun's own commands are candidates too, read
out of `bun --help`: asking bun for its commands is the difference between this
still working when bun grows one and it quietly not.

Wordings captured from bun 1.4.0.

"""

import os
import re
from thebleep import project_context
from thebleep.utils import cache, eager, for_app, replace_command, tool_lines
from thebleep.utils import which

# bun 1.x, and the one line it prints:
#
#   error: Script not found "buidl"
#
# A script may be called anything a JSON string can hold, so the name is taken
# up to the closing quote rather than to the first space.
NOT_FOUND = re.compile(r'Script not found "([^"\r\n]*)"')

# A command in `bun --help` sits at exactly two spaces. The listing is
# two-column and wraps -- `run` has a second line under it reading
# `            lint                 Run a package.json script`, which is an
# example rather than a command -- and that line is indented twelve, so the
# column is what tells one from the other.
COMMAND = re.compile(r'^ {2}(\S+)')

LISTING = 'Commands:'


def _package_json():
    """The `package.json` bun would read, or `None`.

    Upwards from the current directory, which is what bun does: `bun run build`
    works from a subdirectory of the project and the scripts are still the
    project's.

    """
    return project_context.find_up('package.json')


@eager
def _scripts():
    """The names in the project's `scripts`, or nothing."""
    path = _package_json()
    if not path:
        return

    scripts = project_context.package_scripts(os.path.dirname(path))
    if scripts is None:
        return

    yield from scripts


@eager
def _commands():
    """bun's own commands, as `bun --help` lists them."""
    listing = False
    for line in tool_lines(['bun', '--help'], merge_stderr=True):
        if not listing:
            listing = line.strip() == LISTING
            continue

        if line[:1] not in ('', ' '):
            # Back at the left margin, so the listing is over: `Flags:`.
            break

        found = COMMAND.match(line)
        if found and not found.group(1).startswith('<'):
            # `<command> --help` is the last line of the listing, and is the
            # help telling you about itself.
            yield found.group(1)


if which('bun'):
    _commands = cache(which('bun'))(_commands)


@for_app('bun')
def match(command):
    return ('Script not found' in command.output
            and bool(NOT_FOUND.search(command.output)))


def get_new_command(command):
    broken = NOT_FOUND.search(command.output).group(1)
    if not broken:
        return []

    candidates = _scripts()
    if 'run' not in command.script_parts:
        candidates = candidates + [name for name in _commands()
                                   if name not in candidates]

    return replace_command(command, broken, candidates)
