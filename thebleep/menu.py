# -*- encoding: utf-8 -*-

"""The prompt, drawn as a list rather than one line at a time.

The old prompt showed one suggestion, and the down arrow replaced it with the
next: you could not see what else was on offer without walking through it, and
you could not see *what had changed* without reading the two commands against
each other. This draws the suggestions as rows:

    ❯ git status                     95%  from what git printed
      git stash                      75%  from the command
    [enter/↑/↓/tab=edit/?/ctrl+c/esc]  1/2

The words that differ from what was typed are the highlighted ones, so
`cd app && npm run build` reads as three new words in front of the command
you already know. The percentage is the same confidence <kbd>?</kbd> and
`--json` report, and the phrase after it is its basis, shortened.

Nothing here decides anything. It renders a `CommandSelector`'s state and
returns the text to write; `ui.select_command` still reads the keys. The
first draw shows only the first suggestion, because that is all that has
been computed -- the rest of the rules run when the arrow is first pressed,
exactly as before, and the list fills in then.

"""

import os
import sys

from . import const, logs
from .logs import colorama

# How many suggestions are on screen at once. The chosen one stays in view.
ROWS = 3

# A line longer than the terminal wraps, and a wrapped line breaks the count
# of lines to move back over before redrawing. Rows are cut to fit instead.
FALLBACK_WIDTH = 80
ELLIPSIS = u'…'

MARKER = u'❯'

# The confidence bases as `explain.confidence` words them, said shorter.
SHORT_BASIS = {
    'the rule matched captured command output': 'from what it printed',
    'the rule matched the command or local context': 'from the command',
    'a correction learned from the user': 'you taught it',
    'the rule supplied an explicit confidence': 'the rule is sure',
}
BASIS_LENGTH = 40


def terminal_width():
    try:
        return os.get_terminal_size(sys.stderr.fileno()).columns
    except (AttributeError, ValueError, OSError):
        return FALLBACK_WIDTH


def changed_words(original, corrected):
    """`corrected` as words, each paired with whether it is new.

    Word-level, by whitespace: this is for reading, not for running. The
    command that runs is `corrected` exactly as the rule wrote it.

    """
    new_words = corrected.split()
    if original is None:
        return [(word, False) for word in new_words]

    from difflib import SequenceMatcher

    old_words = original.split()
    flagged = []
    matcher = SequenceMatcher(a=old_words, b=new_words, autojunk=False)
    for tag, _, _, start, end in matcher.get_opcodes():
        for word in new_words[start:end]:
            flagged.append((word, tag != 'equal'))
    return flagged


def _short_basis(assessed):
    basis = (assessed.get('basis') or [''])[0]
    if basis in SHORT_BASIS:
        return SHORT_BASIS[basis]
    basis = ' '.join(basis.split())
    if len(basis) > BASIS_LENGTH:
        basis = basis[:BASIS_LENGTH - 1] + ELLIPSIS
    return basis


def _confidence_column(corrected, command):
    from .explain import confidence

    assessed = confidence(getattr(corrected, 'rule', None), command,
                          corrected)
    score = assessed['score']
    if score is None:
        return u''
    return u'{}%  {}'.format(int(round(score * 100)), _short_basis(assessed))


def _visible_length(pieces):
    return sum(len(text) for text, _ in pieces)


def _cut(pieces, width):
    """`pieces` -- (text, style) pairs -- cut to `width` visible characters."""
    if _visible_length(pieces) <= width:
        return pieces
    budget = max(width - 1, 0)
    cut = []
    for text, style in pieces:
        if budget <= 0:
            break
        taken = text[:budget]
        cut.append((taken, style))
        budget -= len(taken)
    cut.append((ELLIPSIS, None))
    return cut


def _paint(pieces):
    reset = logs.color(colorama.Style.RESET_ALL)
    out = []
    for text, style in pieces:
        if style:
            out.append(logs.color(style) + text + reset)
        else:
            out.append(text)
    return u''.join(out)


def row(corrected, command, chosen, width):
    """One suggestion as a line of text, no longer than `width`."""
    original = command.script if command is not None else None
    pieces = [(MARKER if chosen else u' ', colorama.Style.BRIGHT), (u' ', None)]
    words = changed_words(original, corrected.script)
    for index, (word, changed) in enumerate(words):
        if index:
            pieces.append((u' ', None))
        style = colorama.Style.BRIGHT + colorama.Fore.GREEN if changed \
            else (colorama.Style.BRIGHT if chosen else None)
        pieces.append((word, style))
    if corrected.side_effect:
        pieces.append((u' (+side effect)', None))

    column = _confidence_column(corrected, command)
    if column:
        room = width - _visible_length(pieces) - 2
        if room >= len(column):
            pieces.append((u' ' * (room - len(column) + 2), None))
            pieces.append((column, colorama.Style.DIM))
    return _paint(_cut(pieces, width))


def key_hint(offer_edit, offer_explain, position=None, total=None):
    blue = logs.color(colorama.Fore.BLUE)
    green = logs.color(colorama.Fore.GREEN)
    red = logs.color(colorama.Fore.RED)
    reset = logs.color(colorama.Style.RESET_ALL)
    hint = (u'[{green}enter{reset}/{blue}↑{reset}/{blue}↓{reset}{edit}'
            u'{explain}/{red}ctrl+c{reset}/{red}esc{reset}]').format(
        green=green, blue=blue, red=red, reset=reset,
        edit=u'/{}tab{}=edit'.format(blue, reset) if offer_edit else u'',
        explain=u'/{}?{}'.format(blue, reset) if offer_explain else u'')
    if total and total > 1:
        hint += u'  {dim}{position}/{total}{reset}'.format(
            dim=logs.color(colorama.Style.DIM), position=position,
            total=total, reset=reset)
    return hint


def window(index, total):
    """Which rows are on screen: `ROWS` of them, the chosen one among them."""
    if total <= ROWS:
        return 0, total
    start = min(max(index - 1, 0), total - ROWS)
    return start, start + ROWS


class Menu(object):
    """Draws and redraws the list on stderr."""

    def __init__(self, offer_edit, offer_explain, command=None):
        self.offer_edit = offer_edit
        self.offer_explain = offer_explain
        self.command = command
        self.drawn = 0

    def draw(self, commands, index):
        """Write the rows for `commands` with `index` chosen.

        The first draw erases the current line, as the one-line prompt did.
        Every later draw first moves back over what it drew and clears from
        there, so the list is repainted in place rather than scrolled.

        """
        width = terminal_width()
        start, end = window(index, len(commands))
        lines = [row(corrected, self.command, position == index, width)
                 for position, corrected in enumerate(commands)
                 if start <= position < end]
        lines.append(key_hint(self.offer_edit, self.offer_explain,
                              index + 1, len(commands)))

        if self.drawn:
            prefix = u'\r' + logs.escape(u'\033[{}A'.format(self.drawn - 1)) \
                + logs.escape(u'\033[J')
        else:
            prefix = logs.escape(u'\033[1K') + u'\r'

        sys.stderr.write(prefix + const.USER_COMMAND_MARK + u'\n'.join(lines))
        sys.stderr.flush()
        self.drawn = len(lines)


def abstained(tally):
    """Why nothing was offered, from what the correction pass counted."""
    if not tally or not tally.get('rules'):
        return None
    said = u'{} rules for this command; none matched'.format(tally['rules'])
    unread = tally.get('unread', 0)
    if unread:
        said += u', and {} of them needed the output, which was not read'.format(
            unread)
    return said
