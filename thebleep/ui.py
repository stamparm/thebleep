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

        # Arrows, j/k (qwerty), n/e (colemak), and Ctrl+P/Ctrl+N.
        #
        # Ctrl+P is *previous* and Ctrl+N is *next*, which is the other way
        # round from how these were bound. The letter keys follow the colemak
        # argument in `const` -- where `n` sits under a qwerty `j` -- but
        # Ctrl+P and Ctrl+N are not layout arguments, they are the readline
        # bindings every shell's own history uses, and they mean previous and
        # next there.
        if key in (const.KEY_UP, const.KEY_CTRL_P, 'k', 'e'):
            yield const.ACTION_PREVIOUS
        elif key in (const.KEY_DOWN, const.KEY_CTRL_N, 'j', 'n'):
            yield const.ACTION_NEXT
        elif key in (const.KEY_CTRL_C, const.KEY_ESCAPE, 'q'):
            yield const.ACTION_ABORT
        elif key == const.KEY_TAB:
            yield const.ACTION_EDIT
        elif key == const.KEY_QUESTION:
            yield const.ACTION_EXPLAIN
        elif key in ('\n', '\r'):
            yield const.ACTION_SELECT


def _explain_silence():
    """One dim line on what was looked at, when nothing came of it."""
    from . import corrector
    from .menu import abstained

    said = abstained(corrector.last_pass)
    if said:
        logs.dim(said)


def _explain(corrected_command, command):
    """Why this suggestion is being made. Imported here: only asking pays."""
    from . import explain

    logs.explanation(explain.describe(
        corrected_command, command, include_assessment=True))


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

    @property
    def commands(self):
        """What has been computed so far: one, until the list is walked."""
        return self._commands

    @property
    def index(self):
        return self._index


def select_command(corrected_commands, command=None):
    """What to do with which correction.

    Returns a pair of the chosen command and what was asked of it:

     - `(None, ACTION_ABORT)` when ctrl+c was pressed, when nothing matched, or
       when there is no terminal to confirm on;
     - `(command, ACTION_SELECT)` to run it;
     - `(command, ACTION_EDIT)` to hand it to the shell's line editor instead.

    :type corrected_commands: Iterable[thebleep.types.CorrectedCommand]
    :type command: thebleep.types.Command | None
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
        if command is not None:
            _explain_silence()
            from . import stats

            stats.bump('abstained')
        return None, const.ACTION_ABORT

    chosen = const.ACTION_EDIT if wants_edit else const.ACTION_SELECT

    if settings.require_confirmation and settings.auto_run_confidence:
        # Trusted enough to skip the question: see `trust`. Only the first
        # suggestion is ever considered, because that is the one enter would
        # have run, and it is shown along with what let it through.
        from . import trust

        verdict = trust.decide(selector.value, command)
        if verdict:
            logs.show_corrected_command(selector.value)
            logs.trusted(verdict.reason)
            from . import stats

            stats.bump('trusted')
            if settings.explain:
                _explain(selector.value, command)
            return selector.value, chosen
        logs.debug(u'Not run unasked: {}'.format(verdict.reason))

    if not settings.require_confirmation:
        logs.show_corrected_command(selector.value)
        if settings.explain:
            _explain(selector.value, command)
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
    explaining = bool(settings.explain)

    # The list needs to move the cursor back over itself to redraw; a console
    # that renders no escapes gets the one-line prompt it always had.
    menu = None
    if logs._ansi_supported():
        from .menu import Menu

        menu = Menu(offer_edit, offer_explain=True, command=command)

    def show(value):
        if explaining:
            sys.stderr.write('\n')
            _explain(value, command)
        if menu is not None and not explaining:
            menu.draw(selector.commands, selector.index)
        else:
            logs.confirm_text(value, offer_edit, offer_explain=True)

    show(selector.value)

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
        elif action == const.ACTION_EXPLAIN:
            # Once asked, keep answering: walking the suggestions after asking
            # why is asking why about each of them.
            explaining = True
            show(selector.value)
        elif action == const.ACTION_ABORT:
            logs.failed('\nAborted')
            return None, const.ACTION_ABORT
        elif action == const.ACTION_PREVIOUS:
            selector.previous()
            show(selector.value)
        elif action == const.ACTION_NEXT:
            selector.next()
            show(selector.value)

    return None, const.ACTION_ABORT
