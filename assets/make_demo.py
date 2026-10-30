#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Draws the terminal demo in the README as an animated SVG.

An SVG animates inline on GitHub, stays sharp on any display, and is a tenth
the size of the equivalent GIF -- and because it is generated from the script
below, the demo can be corrected in a diff instead of re-recorded.

The animation is CSS only: no SMIL, no JavaScript, nothing that a browser
refuses to run for an image loaded through `<img>`. Every element is given the
same duration and iteration count, so the whole screen restarts as one.

Usage: python assets/make_demo.py [output.svg]

"""

from __future__ import print_function

import io
import sys

# The terminal. A monospace advance width is 0.6em almost everywhere, but not
# quite everywhere, so every line of text is laid out with `textLength` and
# comes out the same width whichever font the reader happens to have.
FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'DejaVu Sans Mono', 'Liberation Mono', monospace")
FONT_SIZE = 15.0
CHAR = FONT_SIZE * 0.6
LINE = 23.0
COLUMNS = 79
PADDING = 24.5           # 79 columns and this padding make the chart's width
CHROME = 28.0            # the title bar, as tall as a macOS window's

# Room around the window for its shadow, which a macOS window always has.
MARGIN = 32.0

# The colours a terminal draws, and only those: what zsh, git and docker print
# is plain text, and what The Bleep's menu colours is what `menu.py` colours --
# the marker and the chosen row bold, the changed word bold green, the
# confidence dim, and the keys green, blue and red. Picked to sit on the
# window's own dark ground, so the demo reads the same in GitHub's light and
# dark themes.
INK = {
    'text': '#d5dae3',
    'bold': '#ffffff',
    'green': '#5fd38d',
    'boldgreen': '#5fd38d',
    'blue': '#6cb6ff',
    'red': '#ff7b72',
    'dim': '#7d8794',
    'prompt': '#d5dae3',
}
BOLD = ('bold', 'boldgreen')

TYPE_MS = 52      # per character
KEY_MS = 190      # after a line is submitted
READ_MS = 620     # to let something printed be read
END_MS = 2100     # holding the last frame before the loop restarts


class Scene(object):
    """A screen being written to, and when each piece of it appears."""

    def __init__(self):
        self.now = 0
        self.row = 0
        self.parts = []

    # -- timeline ---------------------------------------------------------

    def wait(self, ms):
        self.now += ms

    def type(self, prompt, text, then=KEY_MS):
        """Types `text` after `prompt`, a character at a time."""
        started = self.now
        finished = started + len(text) * TYPE_MS
        self.parts.append({'kind': 'prompt', 'row': self.row, 'column': 0,
                           'text': prompt, 'from': started})
        self.parts.append({'kind': 'text', 'row': self.row,
                           'column': len(prompt), 'text': text,
                           'from': started, 'typed_by': finished})
        # The cursor rides the edge of what has been typed, and goes away with
        # the newline rather than sitting there under the output.
        self.parts.append({'kind': 'cursor', 'row': self.row,
                           'column': len(prompt), 'text': text,
                           'from': started, 'typed_by': finished,
                           'until': finished + 110})
        self.now = finished + then
        self.row += 1

    def line(self, *runs):
        """Prints a line, all at once, as a sequence of (colour, text)."""
        column = 0
        for colour, text in runs:
            if text:
                self.parts.append({'kind': colour, 'row': self.row,
                                   'column': column, 'text': text,
                                   'from': self.now})
            column += len(text)
        self.row += 1

    def ambient(self, wrong, what, fixed, output=None):
        """One mistake under `--ambient`, as zsh draws it: the answer shown
        under the line while it is typed, the line rewritten by the first
        return with nothing run, and the fix run by the second -- or, with
        no `output`, left waiting for that return, to end the loop on."""
        started = self.now
        typed = started + len(wrong) * TYPE_MS
        returned = typed + 1500
        run = returned + 1700
        row = self.row
        self.parts.append({'kind': 'prompt', 'row': row, 'column': 0,
                           'text': PROMPT, 'from': started})
        self.parts.append({'kind': 'text', 'row': row, 'column': len(PROMPT),
                           'text': wrong, 'from': started, 'typed_by': typed,
                           'until': returned})
        self.parts.append({'kind': 'cursor', 'row': row, 'column': len(PROMPT),
                           'text': wrong, 'from': started, 'typed_by': typed,
                           'until': returned})
        hint = 'bleep: %s; return runs `%s`' % (what, fixed)
        self.parts.append({'kind': 'text', 'row': row + 1, 'column': 0,
                           'text': hint, 'from': typed + 120,
                           'until': returned})
        self.parts.append({'kind': 'text', 'row': row, 'column': len(PROMPT),
                           'text': fixed, 'from': returned})
        waiting = {'kind': 'cursor', 'row': row, 'column': len(PROMPT) + len(fixed),
                   'text': '', 'from': returned, 'typed_by': returned}
        message = {'kind': 'text', 'row': row + 1, 'column': 0,
                   'text': hint + ', ctrl+_ puts yours back',
                   'from': returned}
        self.parts.extend([waiting, message])
        if output is None:
            self.now = returned
            self.row += 2
            return
        waiting['until'] = message['until'] = run
        self.now = run + KEY_MS
        self.row += 1
        for line in output:
            self.line(('text', line))
        self.wait(900)

    # -- geometry ---------------------------------------------------------

    @property
    def width(self):
        return COLUMNS * CHAR + PADDING * 2

    @property
    def height(self):
        return CHROME + PADDING + self.row * LINE + PADDING * 0.6

    def x(self, column):
        return PADDING + column * CHAR

    def y(self, row):
        return CHROME + PADDING + row * LINE + FONT_SIZE * 0.78


def escape(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;'))


def render(scene, total, at=None):
    """The SVG for `scene`, as one string.

    `at` starts the animation that many milliseconds in, by way of a negative
    delay, which is the only way to see a chosen frame: a headless browser
    screenshots the first frame and no amount of virtual time moves it on.

    """
    def pct(ms):
        return round(100.0 * ms / total, 3)

    offset = '' if at is None else 'animation-delay:-%dms;' % at
    css = [
        '.w{opacity:0;%sanimation-duration:%dms;animation-iteration-count:'
        'infinite;animation-timing-function:steps(1,end)}' % (offset, total),
        '.t{%sanimation-duration:%dms;animation-iteration-count:infinite}'
        % (offset, total),
        'text{font-family:%s;font-size:%gpx;white-space:pre}'
        % (FONT, FONT_SIZE),
        '.cursor{animation:blink 1.1s steps(1,end) infinite}',
        '@keyframes blink{0%,55%{opacity:1}56%,100%{opacity:0}}',
    ]
    body = []

    for index, part in enumerate(scene.parts):
        kind, row, column = part['kind'], part['row'], part['column']
        text, appears = part['text'], part['from']
        x, y = scene.x(column), scene.y(row)

        # When it is on screen. Everything stays until the loop comes round,
        # except a cursor, which leaves with the newline.
        window = 'a%d' % index
        if 'until' in part:
            css.append('@keyframes %s{0%%{opacity:0}%g%%{opacity:1}%g%%'
                       '{opacity:0}}'
                       % (window, pct(appears), pct(part['until'])))
        else:
            css.append('@keyframes %s{0%%{opacity:0}%g%%{opacity:1}}'
                       % (window, pct(appears)))

        if kind == 'cursor':
            # Steps along one character at a time, in step with the typing.
            ride = 'k%d' % index
            columns = len(text)
            if columns:
                css.append('#%s{animation-name:%s;animation-timing-function:'
                           'steps(%d,start)}' % (ride, ride, columns))
                css.append('@keyframes %s{0%%,%g%%{transform:translateX(0)}'
                           '%g%%,100%%{transform:translateX(%gpx)}}'
                           % (ride, pct(appears), pct(part['typed_by']),
                              columns * CHAR))
            body.append(
                '<g class="w" style="animation-name:%s">'
                '<g class="t" id="%s"><rect class="cursor" x="%g" y="%g"'
                ' width="%g" height="%g" fill="%s" opacity="0.8"/></g></g>'
                % (window, ride, x, y - FONT_SIZE * 0.82, CHAR,
                   FONT_SIZE * 1.06, INK['text']))
            continue

        colour = INK.get(kind, INK['text'])
        weight = ' font-weight="bold"' if kind in BOLD else ''
        chunk = ('<text x="%g" y="%g" textLength="%g" lengthAdjust="spacing"'
                 ' fill="%s"%s>%s</text>'
                 % (x, y, len(text) * CHAR, colour, weight, escape(text)))

        if 'typed_by' not in part:
            body.append('<g class="w" style="animation-name:%s">%s</g>'
                        % (window, chunk))
            continue

        # Typed text is clipped by a box that widens one character at a time.
        clip = 'c%d' % index
        columns = len(text)
        css.append('#%s{transform:scaleX(0);transform-origin:%gpx 0;'
                   'animation-name:%s;animation-timing-function:steps(%d,'
                   'start)}' % (clip, x, clip, columns))
        css.append('@keyframes %s{0%%,%g%%{transform:scaleX(0)}%g%%,100%%'
                   '{transform:scaleX(1)}}'
                   % (clip, pct(appears), pct(part['typed_by'])))
        body.append(
            '<clipPath id="%s-p"><rect class="t" id="%s" x="%g" y="%g"'
            ' width="%g" height="%g"/></clipPath>'
            % (clip, clip, x, y - FONT_SIZE, columns * CHAR, LINE))
        body.append('<g class="w" style="animation-name:%s">'
                    '<g clip-path="url(#%s-p)">%s</g></g>'
                    % (window, clip, chunk))

    width, height = scene.width, scene.height
    # A dark-mode macOS window: a title bar a shade lighter than the
    # terminal, a hairline under it, the three buttons at their own size and
    # spacing, a faint light outline, and the shadow every window casts.
    chrome = (
        '.title{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",'
        '"Helvetica Neue","Segoe UI",Roboto,sans-serif;font-size:13px;'
        'font-weight:500}')
    return '\n'.join([
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g"'
        ' width="%g" height="%g" role="img"'
        ' aria-label="The Bleep correcting commands in %s">'
        % (width + MARGIN * 2, height + MARGIN * 2,
           width + MARGIN * 2, height + MARGIN * 2, SHELL_TITLE),
        '<title>The Bleep</title>',
        '<style>%s%s</style>' % (''.join(css), chrome),
        '<defs>'
        '<filter id="shadow" x="-10%%" y="-10%%" width="120%%" height="130%%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#000"'
        ' flood-opacity="0.38"/></filter>'
        '<clipPath id="window"><rect width="%g" height="%g" rx="10"/>'
        '</clipPath>'
        '<linearGradient id="bar" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#30333a"/>'
        '<stop offset="1" stop-color="#282b31"/></linearGradient>'
        '</defs>' % (width, height),
        '<g transform="translate(%g,%g)">' % (MARGIN, MARGIN),
        '<rect width="%g" height="%g" rx="10" fill="#15181f"'
        ' filter="url(#shadow)"/>' % (width, height),
        '<g clip-path="url(#window)">'
        '<rect width="%g" height="%g" fill="url(#bar)"/>'
        '<rect y="%g" width="%g" height="1" fill="#0c0e12"/></g>'
        % (width, CHROME, CHROME, width),
        '<rect x="0.5" y="0.5" width="%g" height="%g" rx="9.5" fill="none"'
        ' stroke="#ffffff" stroke-opacity="0.13"/>' % (width - 1, height - 1),
        # Close, minimise and zoom, as a focused window has them.
        '<circle cx="20" cy="14" r="6" fill="#ff5f57" stroke="#e0443e"'
        ' stroke-width="0.5"/>',
        '<circle cx="40" cy="14" r="6" fill="#febc2e" stroke="#dea123"'
        ' stroke-width="0.5"/>',
        '<circle cx="60" cy="14" r="6" fill="#28c840" stroke="#1aab29"'
        ' stroke-width="0.5"/>',
        '<text class="title" x="%g" y="18.5" text-anchor="middle"'
        ' fill="#a9aeb6">%s</text>' % (width / 2, escape(TITLE)),
        '\n'.join(body),
        '</g>',
        '</svg>',
        ''])


# The shell this is, in the title bar: what return does under `--ambient`
# differs by shell -- zsh rewrites the line before it runs, bash lets it fail
# and has the fix at the next prompt -- and the messages drawn are zsh's own.
SHELL_TITLE = 'zsh'
# What Terminal puts in that bar: the directory, then the shell.
TITLE = u'project \u2014 %s' % SHELL_TITLE
# And its prompt as zsh draws it by default for a user who is not root.
PROMPT = '% '
MARKER = '❯'


def demo():
    """Slips caught before they run, and one fixed after it failed.

    Every suggestion here is the one the rules really produce: each was run
    through `match` and `get_new_command` before being drawn, and the errors
    above them are what the tools themselves print. The `--ambient` lines
    and their messages are what zsh showed when driven through them.

    """
    scene = Scene()
    scene.wait(500)

    # A mistyped program, and a mistyped subcommand, caught at return.
    status = ['On branch feature', 'nothing to commit, working tree clean']
    scene.ambient('gti status', 'gti is not a command', 'git status', status)
    scene.ambient('git satus', 'satus is not a git command', 'git status',
                  status)

    # One that has to fail first: a branch that is not there. With nothing
    # reading the terminal, `bleep` asks before running it again to read what
    # it printed -- the line wraps where an 79-column terminal wraps it.
    scene.type(PROMPT, 'git checkout mian', then=260)
    scene.line(('text', "error: pathspec 'mian' did not match any file(s) "
                        "known to git"))
    scene.wait(READ_MS)
    scene.type(PROMPT, 'bleep', then=380)
    scene.line(('bold', 'git checkout mian'),
               ('text', ' has to run again to be read, and anything it '
                        'changes will cha'))
    scene.line(('text', 'nge twice. Run it? ['), ('green', 'y'),
               ('text', '/'), ('red', 'N'), ('text', '] '))
    scene.wait(900)
    scene.parts.append({'kind': 'text', 'row': scene.row - 1,
                        'column': len('nge twice. Run it? [y/N] '),
                        'text': 'yes', 'from': scene.now})
    scene.wait(600)
    confidence = '95%  from what it printed'
    chosen = MARKER + ' git checkout main'
    scene.line(('bold', MARKER), ('text', ' '), ('bold', 'git'),
               ('text', ' '), ('bold', 'checkout'), ('text', ' '),
               ('boldgreen', 'main'),
               ('text', ' ' * (COLUMNS - len(chosen) - len(confidence))),
               ('dim', confidence))
    scene.line(('text', '['), ('green', 'enter'), ('text', '/'),
               ('blue', '\u2191'), ('text', '/'), ('blue', '\u2193'),
               ('text', '/'), ('blue', 'tab'), ('text', '=edit/'),
               ('blue', '?'), ('text', '/'), ('red', 'ctrl+c'), ('text', '/'),
               ('red', 'esc'), ('text', ']'))
    scene.wait(1300)
    scene.line(('text', "Switched to branch 'main'"))
    scene.wait(700)

    # And the loop ends where it began, on a line not yet run.
    scene.ambient('dokcer ps', 'dokcer is not a command', 'docker ps')

    return scene, scene.now + END_MS


def main(argv):
    at = None
    if '--at' in argv:
        index = argv.index('--at')
        at = int(argv[index + 1])
        argv = argv[:index] + argv[index + 2:]

    scene, total = demo()

    # The loop starts on the finished screen rather than on an empty one.
    # Anywhere the animation does not run -- a reader who scrolled past, a
    # printed page, a client that renders the first frame and stops -- an empty
    # terminal is a wasted picture, and the whole correction is the useful one.
    if at is None:
        at = scene.now

    svg = render(scene, total, at)
    path = argv[1] if len(argv) > 1 else 'assets/demo.svg'
    # Explicitly UTF-8: the demo is full of box-drawing and arrow characters,
    # and writing them through a machine's default encoding fails outright on
    # Windows.
    with io.open(path, 'w', encoding='utf-8') as handle:
        handle.write(svg)
    print('%s: %g x %g, %.1fs loop, %d bytes'
          % (path, scene.width, scene.height, total / 1000.0, len(svg)))


if __name__ == '__main__':
    main(sys.argv)
