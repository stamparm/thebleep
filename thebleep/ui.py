# -*- encoding: utf-8 -*-

import os
import sys
from .conf import settings
from .exceptions import NoRuleMatched
from .system import get_key
from .utils import get_alias
from . import logs, const


def is_interactive():
    """Check if stdin is a TTY (interactive terminal)."""
    try:
        return os.isatty(sys.stdin.fileno())
    except (AttributeError, ValueError):
        return False


def read_actions():
    """Yields actions for pressed keys."""
    while True:
        key = get_key()

        # Handle arrows, j/k (qwerty), and n/e (colemak)
        if key in (const.KEY_UP, const.KEY_CTRL_N, 'k', 'e'):
            yield const.ACTION_PREVIOUS
        elif key in (const.KEY_DOWN, const.KEY_CTRL_P, 'j', 'n'):
            yield const.ACTION_NEXT
        elif key in (const.KEY_CTRL_C, const.KEY_ESCAPE, 'q'):
            yield const.ACTION_ABORT
        elif key == const.KEY_TAB:
            yield const.ACTION_EDIT
        elif key in ('\n', '\r'):
            yield const.ACTION_SELECT


class CommandSelector(object):
    """Helper for selecting rule from rules list."""

    def __init__(self, commands):
        """:type commands: Iterable[thebleep.types.CorrectedCommand]"""
        self._commands_gen = commands
        try:
            self._commands = [next(self._commands_gen)]
        except StopIteration:
            raise NoRuleMatched
        self._realised = False
        self._index = 0

    def _realise(self):
        if not self._realised:
            self._commands += list(self._commands_gen)
            self._realised = True

    def next(self):
        self._realise()
        self._index = (self._index + 1) % len(self._commands)

    def previous(self):
        self._realise()
        self._index = (self._index - 1) % len(self._commands)

    @property
    def value(self):
        """:rtype thebleep.types.CorrectedCommand"""
        return self._commands[self._index]


def select_command(corrected_commands):
    """What to do with which correction.

    Returns a pair of the chosen command and what was asked of it:

     - `(None, ACTION_ABORT)` when ctrl+c was pressed, when nothing matched, or
       when there is no terminal to confirm on;
     - `(command, ACTION_SELECT)` to run it;
     - `(command, ACTION_EDIT)` to hand it to the shell's line editor instead.

    :type corrected_commands: Iterable[thebleep.types.CorrectedCommand]
    :rtype: (thebleep.types.CorrectedCommand | None, thebleep.const._GenConst)

    """
    # Imported here rather than at the top so that a test replacing
    # `thebleep.shells.shell` is the one that answers.
    from .shells import shell

    # Nushell has no way to run a string in the session it is running in, so
    # there every correction goes to the line editor and the user submits it.
    # See `shells.nushell`.
    must_edit = not shell.can_run_corrections()

    # Whether the shell on the other end of the alias can take a command back
    # for editing. Asked once: it decides both what the prompt offers and
    # whether `--edit` can be honoured at all.
    editable = must_edit or const.can_edit()
    wants_edit = must_edit or bool(settings.edit)

    if wants_edit and not editable:
        logs.cannot_edit()
        return None, const.ACTION_ABORT

    try:
        selector = CommandSelector(corrected_commands)
    except NoRuleMatched:
        logs.failed('No bleeps given' if get_alias() == 'bleep'
                    else 'Nothing found')
        return None, const.ACTION_ABORT

    chosen = const.ACTION_EDIT if wants_edit else const.ACTION_SELECT

    if not settings.require_confirmation:
        logs.show_corrected_command(selector.value)
        return selector.value, chosen

    if not is_interactive():
        # Nobody is there to confirm, so show what we'd run and leave the
        # decision to whoever reads the output.
        logs.show_corrected_command(selector.value)
        logs.failed('Aborted: no terminal to confirm on, rerun with --yes')
        return None, const.ACTION_ABORT

    # With `--edit` the question is still which suggestion, only the answer
    # goes to the line editor rather than to the shell.
    offer_edit = editable and not wants_edit
    logs.confirm_text(selector.value, offer_edit)

    for action in read_actions():
        if action == const.ACTION_SELECT:
            sys.stderr.write('\n')
            return selector.value, chosen
        elif action == const.ACTION_EDIT:
            if not offer_edit:
                # Not offered, so nothing was promised: tab does nothing rather
                # than something the shell cannot carry out.
                continue
            sys.stderr.write('\n')
            return selector.value, const.ACTION_EDIT
        elif action == const.ACTION_ABORT:
            logs.failed('\nAborted')
            return None, const.ACTION_ABORT
        elif action == const.ACTION_PREVIOUS:
            selector.previous()
            logs.confirm_text(selector.value, offer_edit)
        elif action == const.ACTION_NEXT:
            selector.next()
            logs.confirm_text(selector.value, offer_edit)

    return None, const.ACTION_ABORT
