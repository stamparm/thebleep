# -*- encoding: utf-8 -*-

"""`zypper isntall vim` -> `zypper install vim`, on openSUSE and SLE.

zypper says which word it did not understand and then does not say what it could
have been:

    $ zypper isntall vim
    Unknown command 'isntall'
    Type 'zypper help' to get a list of global options and commands.

So the candidates are asked for. `zypper --help` lists every command with its
abbreviations -- `install, in`, `dist-upgrade, dup`, `info, if, show` -- and
those abbreviations are half of what gets mistyped, so they are candidates too:
`zypper dpu` comes back as `zypper dup`.

Read out of `--help` rather than written down here, for the same reason the dnf
and yum rules do it: a list in a rule file is a snapshot of whichever zypper the
author had, and zypper has gained commands in every release. Asking costs a
process, and it is only asked once a command has already failed with a word
zypper did not recognise.

"""

import re
from thebleep.specific.sudo import sudo_support
from thebleep.specific.zypper import zypper_available
from thebleep.utils import (cache, for_app, replace_command, which,
                            tool_output)

# `Unknown command 'isntall'`, and nothing else in that message is wanted.
UNKNOWN = re.compile(r"Unknown command '([^']+)'")

# What a command looks like in `zypper --help`: exactly six spaces of indent,
# then the name and its abbreviations, then two or more spaces before the
# description. The description's own continuation lines are indented twenty-eight
# and the section headings two, so neither is mistaken for a command.
LISTED = re.compile(r'(?m)^ {6}(\S[^\n]*?)(?:  |$)')


@sudo_support
@for_app('zypper')
def match(command):
    return "unknown command '" in command.output.lower()


def _parse_operations(help_text):
    """Every command and abbreviation `zypper --help` lists."""
    if 'Commands:' in help_text:
        # Below this heading are the commands; above it are the global options.
        help_text = help_text[help_text.index('Commands:'):]

    found = []
    for listed in LISTED.findall(help_text):
        for name in listed.split(','):
            name = name.strip()
            # `help, ?` is the one entry whose abbreviation is punctuation, and
            # nobody mistypes their way to it.
            if name and name != '?':
                found.append(name)
    return found


def _get_operations():
    return _parse_operations(tool_output(['zypper', '--help']))


if which('zypper'):
    _get_operations = cache(which('zypper'))(_get_operations)


@sudo_support
def get_new_command(command):
    found = UNKNOWN.findall(command.output)
    if not found:
        # `match` looked for the message without regard to case; if the wording
        # ever moves far enough that the name cannot be read out of it, that is
        # not worth raising over.
        return []
    return replace_command(command, found[0], _get_operations())


enabled_by_default = zypper_available
