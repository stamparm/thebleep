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

import sys

# The terminal. A monospace advance width is 0.6em almost everywhere, but not
# quite everywhere, so every line of text is laid out with `textLength` and
# comes out the same width whichever font the reader happens to have.
FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'DejaVu Sans Mono', 'Liberation Mono', monospace")
FONT_SIZE = 15.0
CHAR = FONT_SIZE * 0.6
LINE = 23.0
COLUMNS = 74
PADDING = 22.0
CHROME = 36.0

# Terminal colours, close enough to a default palette to look familiar and
# picked to sit on the window's own dark ground rather than the page's, so the
# demo reads the same in GitHub's light and dark themes.
INK = {
    'text': '#d5dae3',
    'dim': '#7d8794',
    'prompt': '#5fd38d',
    'error': '#ff7b72',
    'accent': '#ffb454',
    'cyan': '#6cb6ff',
}

TYPE_MS = 62      # per character
KEY_MS = 190      # after a line is submitted
READ_MS = 900     # to let something printed be read
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

    def waiting(self, prompt):
        """Leaves a prompt with the cursor blinking on it."""
        self.parts.append({'kind': 'prompt', 'row': self.row, 'column': 0,
                           'text': prompt, 'from': self.now})
        self.parts.append({'kind': 'cursor', 'row': self.row,
                           'column': len(prompt), 'text': '',
                           'from': self.now, 'typed_by': self.now})
        self.row += 1

    def blank(self):
        self.row += 1

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

        colour = INK['prompt'] if kind == 'prompt' else INK.get(kind,
                                                                INK['text'])
        chunk = ('<text x="%g" y="%g" textLength="%g" lengthAdjust="spacing"'
                 ' fill="%s">%s</text>'
                 % (x, y, len(text) * CHAR, colour, escape(text)))

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
    return '\n'.join([
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g"'
        ' width="%g" height="%g" role="img"'
        ' aria-label="The Bleep correcting a command in a terminal">'
        % (width, height, width, height),
        '<title>The Bleep</title>',
        '<style>%s</style>' % ''.join(css),
        '<rect width="%g" height="%g" rx="10" fill="#15181f"/>'
        % (width, height),
        '<rect x="0.5" y="0.5" width="%g" height="%g" rx="9.5" fill="none"'
        ' stroke="#2b313c"/>' % (width - 1, height - 1),
        '<circle cx="24" cy="18" r="5" fill="#42474f"/>',
        '<circle cx="43" cy="18" r="5" fill="#42474f"/>',
        '<circle cx="62" cy="18" r="5" fill="#42474f"/>',
        '<text x="%g" y="22.5" text-anchor="middle" fill="#6d7682"'
        ' font-size="12.5">bleep</text>' % (width / 2),
        '\n'.join(body),
        '</svg>',
        ''])


def demo():
    """The scene: the mistake everybody has made, and what happens next."""
    scene = Scene()
    scene.wait(600)
    scene.type('$ ', 'apt-get install vim', then=320)
    scene.line(('error', 'E: Could not open lock file /var/lib/dpkg/lock-'
                         'frontend - open (13:'))
    scene.line(('error', '   Permission denied)'))
    scene.wait(READ_MS)
    scene.blank()
    scene.type('$ ', 'bleep', then=420)
    scene.line(('accent', 'sudo '), ('text', 'apt-get install vim '),
               ('dim', '[enter/↑/↓/ctrl+c/esc]'))
    scene.wait(1200)
    scene.line(('cyan', 'Reading package lists... Done'))
    scene.wait(160)
    scene.line(('cyan', 'Building dependency tree... Done'))
    scene.wait(160)
    scene.line(('text', 'The following NEW packages will be installed:'))
    scene.line(('prompt', '  vim'))
    scene.wait(240)
    scene.waiting('$ ')
    return scene, scene.now + END_MS


def main(argv):
    at = None
    if '--at' in argv:
        index = argv.index('--at')
        at = int(argv[index + 1])
        argv = argv[:index] + argv[index + 2:]

    scene, total = demo()
    svg = render(scene, total, at)
    path = argv[1] if len(argv) > 1 else 'assets/demo.svg'
    with open(path, 'w') as handle:
        handle.write(svg)
    print('%s: %g x %g, %.1fs loop, %d bytes'
          % (path, scene.width, scene.height, total / 1000.0, len(svg)))


if __name__ == '__main__':
    main(sys.argv)
