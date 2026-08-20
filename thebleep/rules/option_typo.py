# -*- encoding: utf-8 -*-

"""`ls --colour` -> `ls --color`. A mistyped long option, for any program.

The third kind of framework rule, after `clap_suggestion` and
`cobra_suggestion`, and the least glamorous: there is no framework here, only a
convention every command line tool has followed for forty years. A long option
starts with two dashes, and a program that does not recognise one says so in one
of a handful of ways:

    $ ls --colour
    ls: unrecognized option '--colour'
    Try 'ls --help' for more information.

    $ git status --shrot
    error: unknown option `shrot'
    usage: git status [<options>] [--] [<pathspec>...]

        -s, --[no-]short      show status concisely

    $ curl --verbse http://x
    curl: option --verbse: is unknown

    $ tar --extrat -f x.tar
    tar: unrecognized option '--extrat'

None of that was corrected before. A mistyped flag is at least as common as a
mistyped subcommand, and until now the only rule that fired on any of it was
`long_form_help`, which answered `ls --help` -- a help screen offered as though
it were the fix, with the rest of your command thrown away.

Where the answer comes from, in order:

1. **The output**, when the program printed its options -- which git does, so
   `git status --shrot` needs nothing else run.
2. **`<program> --help`**, when it did not -- and only when the program's own
   message said to. `ls`, `tar`, `curl`, `sort` and the rest all end with
   `Try 'ls --help' for more information.`, which is an invitation, and running
   what a program invites you to run is a different thing from guessing that
   some unknown program's `--help` is harmless. Without that line, nothing is
   run. `git` is asked `git <subcommand> -h`, which is where git keeps a
   subcommand's options.

`git log --onelien` is a known miss: `--oneline` is in git's manual page rather
than in `git log -h`, so it is not among the options git offers and nothing here
invents it.

Then `thebleep.matching` picks the nearest, so a transposition counts as the one
slip it is. Nothing is offered when nothing is close: `--colour` reaches
`--color`, and a flag that was never a flag reaches nothing.

Wordings captured from GNU coreutils 9.x, tar 1.35, curl 8.x and git 2.47.3.

"""

import re
from thebleep import matching
from thebleep.shells import shell
from thebleep.utils import memoize, replace_argument, which

# Every way a program says it did not know a long option. The name is captured
# with or without its dashes, because git reports `shrot` for `--shrot`.
BROKEN = (
    # GNU: ls, tar, sort, and most of coreutils.
    re.compile(r"unrecognized option '?-{1,2}([A-Za-z0-9][\w-]*)'?"),
    # git, three different ways.
    re.compile(r"unknown option `-{0,2}([A-Za-z0-9][\w-]*)'"),
    re.compile(r'(?:invalid|unknown) option: -{1,2}([A-Za-z0-9][\w-]*)'),
    re.compile(r'unrecognized argument: -{1,2}([A-Za-z0-9][\w-]*)'),
    # curl.
    re.compile(r'option -{1,2}([A-Za-z0-9][\w-]*): is unknown'),
)

# A long option as it appears in a usage block. git writes `--[no-]short` for a
# flag that can be negated, and the name wanted is `short`.
OPTION = re.compile(r'--(?:\[no-\])?([A-Za-z0-9][\w-]*)')

# Enough of the wording for the rule pack to skip this rule when it cannot
# apply. `for_app` is absent on purpose: the program is not known in advance.
MARKERS = ('unrecognized option', 'unknown option', 'invalid option',
           'unrecognized argument', ': is unknown')


def _broken(output):
    """The option name the program did not recognise."""
    for pattern in BROKEN:
        found = pattern.search(output)
        if found:
            return found.group(1)

    return None


def _as_typed(script_parts, name):
    """The argument in the command that holds `name`, dashes and all.

    git reports `shrot` where the user typed `--shrot`, so the thing to replace
    is found in the command rather than in the message.

    """
    for part in script_parts:
        if part.startswith('-') and part.lstrip('-').split('=')[0] == name:
            return part

    return None


@memoize
def _options_from_help(program, subcommand):
    """The long options `program` says it has, asked of `program`.

    Only reached when the program did not print them. `git` keeps a
    subcommand's options behind `git <subcommand> -h`; everything else answers
    `--help`.

    Several programs -- git among them -- exit non-zero when asked for help, and
    the text is on the exception rather than the return value. Treating that as
    a failure is how this came to answer nothing for exactly the programs it was
    written for.

    """
    from subprocess import CalledProcessError, PIPE, run, TimeoutExpired
    from thebleep.utils import DEVNULL

    if program == 'git' and subcommand:
        arguments = (program, subcommand, '-h')
    else:
        arguments = (program, '--help')

    try:
        finished = run(arguments, stdout=PIPE, stderr=PIPE, stdin=DEVNULL,
                       timeout=5)
    except (OSError, CalledProcessError, TimeoutExpired, ValueError):
        return []

    printed = (finished.stdout + finished.stderr).decode('utf-8', 'replace')
    return OPTION.findall(printed)


# Options every program has and nobody means. `ls: unrecognized option
# '--colour'` is followed by `Try 'ls --help'`, so reading the output naively
# finds exactly one candidate -- `help` -- and stops there, never asking the
# program what its options actually are. That is how `--colour` came to be
# answered with `--help`.
BOILERPLATE = frozenset({'help', 'usage', 'version', 'manual'})


def _candidates(command, broken):
    """Long options this program might have meant, best source first."""
    from_output = [name for name in OPTION.findall(command.output)
                   if name != broken and name not in BOILERPLATE]
    if from_output:
        return from_output

    # Only ask the program when the program said to ask it. Everything that
    # needs this prints `Try 'x --help' for more information.`; a program that
    # does not invite it is not run.
    if '--help' not in command.output and ' -h ' not in command.output:
        return []

    parts = command.script_parts
    subcommand = None
    for part in parts[1:]:
        if not part.startswith('-'):
            subcommand = part
            break

    return [name for name in _options_from_help(parts[0], subcommand)
            if name != broken and name not in BOILERPLATE]


def match(command):
    return (('unrecognized option' in command.output
             or 'unknown option' in command.output
             or 'invalid option' in command.output
             or 'unrecognized argument' in command.output
             or ': is unknown' in command.output)
            and bool(command.script_parts)
            and bool(which(command.script_parts[0]))
            and bool(_broken(command.output))
            and bool(_as_typed(command.script_parts, _broken(command.output))))


def get_new_command(command):
    broken = _broken(command.output)
    typed = _as_typed(command.script_parts, broken)

    ranked = matching.rank(broken, _candidates(command, broken), limit=3)

    # The dashes come from what was typed, so `--colour` is answered with
    # `--color` and a short flag stays short.
    dashes = typed[:len(typed) - len(typed.lstrip('-'))]
    # Quoted: the name was read out of a program's own usage text, and this
    # goes back to the shell to be evaluated.
    return [replace_argument(command.script, typed, shell.quote(dashes + name))
            for name in ranked]


# Ahead of `long_form_help`, which fires on the same output and answers
# `ls --help` -- a help screen dressed as a correction, with the rest of the
# command discarded. When there is a real option to offer, it is the better
# answer; when there is not, this says nothing and the old behaviour is still
# there behind it.
priority = 900
