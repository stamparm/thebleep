"""The same command from your history, with the one slip put right.

This used to be any history line within difflib's 0.6 of the whole command,
whether or not the command had failed -- so `mkdir dir1` offered `git rm
dir1`, `git push origin mian` offered `git push --force origin main`, and an
`rm -rf` that had succeeded offered the `sudo rm -rf` of another path. A
history line only stands in for the command now when it has the same number
of words and differs in exactly one of them, that one is a near spelling of
it, and it adds no privilege, deletion or `--force` the command did not
already have. A command that exited 0 is not corrected from history at all.

"""

from thebleep.types import CorrectedCommand
from thebleep.utils import get_close_matches, \
    get_valid_history_without_current


def _words(script):
    from thebleep.shells import shell

    try:
        return shell.split_command(script)
    except ValueError:
        return None


def _markers(script):
    # Imported here: this rule runs on every correction, and only one with a
    # history line one slip away needs the scan.
    from thebleep import risk

    return set(risk.assess(CorrectedCommand(script, None, 0))['factors'])


def _one_slip_away(command):
    """History lines that are `command` with one word spelled differently,
    in the order history has them."""
    from thebleep import replay

    if replay.previous_status() == 0:
        return []
    typed = command.script_parts
    if not typed:
        return []
    found = []
    allowed = None
    for line in get_valid_history_without_current(command):
        words = _words(line)
        if not words or len(words) != len(typed):
            continue
        changed = [(mine, theirs) for mine, theirs in zip(typed, words)
                   if mine != theirs]
        if len(changed) != 1:
            continue
        mine, theirs = changed[0]
        if not get_close_matches(mine, [theirs], 1):
            continue
        if allowed is None:
            allowed = _markers(command.script)
        if not _markers(line) <= allowed:
            continue
        found.append(line)
    return found


def match(command):
    return bool(_one_slip_away(command))


def get_new_command(command):
    candidates = _one_slip_away(command)
    return get_close_matches(command.script, candidates, cutoff=0) \
        or candidates[:1]


priority = 9999


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
