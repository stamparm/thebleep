# -*- encoding: utf-8 -*-

"""`gh reop list` -> `gh repo list`, for any tool built with cobra.

The companion to `clap_suggestion`, for the other half of the modern command
line. cobra is what most Go tools use, and its answer is as regular as clap's:

    $ gh reop list
    unknown command "reop" for "gh"

    Did you mean this?
        repo

    $ helm instal mychart
    Error: unknown command "instal" for "helm"

    Did you mean this?
        install

    $ gh ise list
    unknown command "ise" for "gh"

    Did you mean this?
        gist
        issue

So `gh`, `helm`, `hugo`, `etcdctl`, `istioctl` and anything else written with it
are corrected without a line being added here for any of them.

Three prefixes are in the wild -- bare, `Error:` and `error:` -- and the
suggestions are always one indented name per line after `Did you mean this?`.
Captured from gh 2.63.2, helm 3.16.3, kubectl 1.31.0 and docker 27.3.1.

A mistyped *flag* is not covered, because cobra does not offer anything for one:
`helm ls --al` answers `Error: unknown flag: --al` and stops. Nothing to read,
so nothing to suggest.

"""

import re
from thebleep.types import Suggestion
from thebleep.utils import replace_command

# `unknown command "reop" for "gh"`, with or without an `Error:`/`error:` in
# front of it. The name of the program is in there too and is deliberately
# ignored -- the point is not to care which program this is.
BROKEN = re.compile(r'unknown command "([^"]+)" for "[^"]*"')

# One indented name per line, after the marker, until the block ends. cobra
# writes a tab; accepting any leading whitespace costs nothing and survives a
# terminal or a pager that has expanded it.
MARKER = 'Did you mean this?'
SUGGESTION = re.compile(r'^\s+(\S+)\s*$')


def _broken(output):
    found = BROKEN.search(output)
    return found.group(1) if found else None


def _suggestions(output):
    """The names cobra offered, in the order it offered them."""
    lines = output.split('\n')
    for index, line in enumerate(lines):
        if MARKER in line:
            break
    else:
        return []

    found = []
    for line in lines[index + 1:]:
        if not line.strip():
            # cobra puts a blank line between the list and whatever follows,
            # and `Usage:` follows -- so the first empty line ends the list.
            if found:
                break
            continue

        suggestion = SUGGESTION.match(line)
        if not suggestion:
            break

        found.append(suggestion.group(1))

    return found


def match(command):
    # The literal is written out rather than referring to `MARKER`, because
    # `rulepack` extracts literals and cannot follow a name -- and a rule with
    # no output clause is loaded for every correction, which is the cost this
    # whole design is meant to avoid.
    return ('Did you mean this?' in command.output
            and bool(_broken(command.output))
            and bool(_suggestions(command.output)))


def get_new_command(command):
    return [Suggestion(fixed, confidence=0.98, evidence=(
        'cobra named this replacement in the command error',))
        for fixed in replace_command(command, _broken(command.output),
                                     _suggestions(command.output))]
