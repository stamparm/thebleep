# -*- encoding: utf-8 -*-

"""`go biuld` -> `go build`, for any program whose manual lists its commands.

The tools that print a suggestion have rules that read it: git's "most
similar command", cobra's and clap's "did you mean". This is for the ones
that name the broken word and stop:

    $ go biuld ./...
    go biuld: unknown command
    Run 'go help' for usage.

    $ docker pss
    docker: 'pss' is not a docker command.
    See 'docker --help'

    $ cargo zzzqqq
    error: no such command: `zzzqqq`

Where the candidates come from is `thebleep.vocabulary`: the program's manual
pages -- `git-status.1`, `docker-image-ls.1`, `cargo-build.1`, one per
subcommand, so the file names are the list -- and its fish completion. Both
are files on this machine, read without running anything, and both are only
*candidates*: `matching.rank` holds them to edit distance, so `go zzzz` is
still answered with nothing.

Tool-specific rules that ask the program for its list (`go help`, `docker
--help`) run first and are usually right; this comes after them, for the
programs nobody wrote a rule for, and for the machines where the program's
own list could not be read. Outputs that *do* name a candidate are left to the
rules that read one.

Wordings captured from Go 1.22, Docker 20.10, cargo 1.98 and git 2.43.

"""

import re

from thebleep import matching, vocabulary
from thebleep.shells import shell
from thebleep.utils import command_word_index, replace_argument, which

priority = 1200

# The broken word, in each wording. The word is then looked for in the
# command, so a message that names something not typed is not acted on.
BROKEN = (
    # go: `go biuld: unknown command`
    re.compile(r'^\S+ (\S+): unknown command', re.MULTILINE),
    # git, docker: `docker: 'pss' is not a docker command.`
    re.compile(r"'([^'\r\n]+)' is not a \S+ command"),
    # cargo: error: no such command: `zzzqqq`
    re.compile(r'no such command: `([^`\r\n]+)`'),
    # brew and the general form: `Error: Unknown command: isntall`,
    # `unknown command "gt"`, `unknown subcommand 'foo'`
    re.compile(r'[Uu]nknown (?:sub)?command:? ["`\']?([A-Za-z0-9][\w.-]*)'),
)

# When the output already names the answer, another rule reads it.
NAMED = ('Did you mean', 'did you mean', 'most similar', 'maybe you meant',
         'Similar command')


def _broken(output):
    for pattern in BROKEN:
        found = pattern.search(output)
        if found:
            return found.group(1)
    return None


def match(command):
    return (('unknown command' in command.output
             or 'Unknown command' in command.output
             or 'no such command' in command.output
             or "' is not a " in command.output)
            and not any(name in command.output for name in NAMED)
            and len(command.script_parts) >= 2
            and bool(_broken(command.output)))


def _program_and_prefix(parts, broken):
    """The program, and the subcommand words typed before the broken one."""
    start = command_word_index(parts)
    if start >= len(parts):
        return None, None
    program = parts[start]
    prefix = []
    for part in parts[start + 1:]:
        if part == broken:
            return program, tuple(prefix)
        if not part.startswith('-'):
            prefix.append(part)
    return None, None


def get_new_command(command):
    broken = _broken(command.output)
    program, prefix = _program_and_prefix(command.script_parts, broken)
    if program is None or not which(program):
        return []

    candidates = vocabulary.subcommands(program, prefix)
    if not candidates:
        return []

    return [replace_argument(command.script, broken, shell.quote(candidate))
            for candidate in matching.rank(broken, candidates, limit=3)]
