#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Draws the benchmark chart in the README from the recorded run.

The numbers are read from `bench/results/final.json`, the run committed with
the harness, so the picture cannot drift away from the measurement: regenerate
it after a new run and the chart and the table have to agree.

Bars are scaled against *The Fuck*'s time for the same scenario, so a row
compares the two rather than comparing a shell startup against a megabyte of
build output. Absolute milliseconds are printed beside every bar.

Two files come out: the light one is what most people see, and the dark one is
picked up by the `<picture>` element in the README for a reader on a dark
theme. Both carry their own background, so whichever one a client falls back to
is still legible on the other theme's page.

Usage: python assets/make_benchmark.py

"""

from __future__ import print_function

import json
import os
import sys

# GitHub's own type stack, so the chart looks like the page it sits on.
SANS = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', "
        "Helvetica, Arial, sans-serif")
MONO = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")

WIDTH = 760.0
PADDING = 28.0
LABEL = 206.0            # width of the scenario column
SPEEDUP = 62.0           # width of the speedup column
GUTTER = 72.0            # room after the longest bar for its own figure
BAR = 9.0                # bar thickness
BAR_GAP = 6.0
ROW = 54.0
HEAD = 50.0
FOOT = 32.0

# Light first, and GitHub's palette for both: the greens and greys are the ones
# the page around the chart is already using.
THEMES = {
    'light': {
        'card': '#ffffff',
        'edge': '#d1d9e0',
        'label': '#1f2328',
        'dim': '#59636e',
        'fuck': '#d1d9e0',
        'bleep': '#1f883d',
        'accent': '#953800',
    },
    'dark': {
        'card': '#0d1117',
        'edge': '#30363d',
        'label': '#e6edf3',
        'dim': '#9198a1',
        'fuck': '#30363d',
        'bleep': '#3fb950',
        'accent': '#d29922',
    },
}

# The scenarios worth showing, in the order they are worth reading, with the
# names the harness gives them. `version` is left out as a second measurement
# of the same startup cost as `alias`.
SCENARIOS = [
    ('alias', 'Open a shell'),
    ('correct-fast', 'Correct a mistyped command'),
    ('correct-in-repo', 'Correct inside a git repository'),
    ('correct-nomatch', 'Correct when nothing matches'),
    ('correct-slow', 'Correct a slow command *'),
    ('correct-big-output', 'Correct after 1 MB of output'),
]


def escape(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;'))


def milliseconds(value):
    if value >= 1000:
        return '%.2f s' % (value / 1000.0)
    if value >= 10:
        return '%d ms' % round(value)
    return '%.1f ms' % value


def rows(results):
    subjects = results['subjects']
    for name, label in SCENARIOS:
        before = subjects['fuck']['scenarios'].get(name)
        after = subjects['bleep']['scenarios'].get(name)
        if before and after:
            yield label, before['median'], after['median']


def render(results, theme):
    ink = THEMES[theme]
    measured = list(rows(results))
    height = HEAD + len(measured) * ROW + FOOT
    plot = WIDTH - PADDING * 2 - LABEL - SPEEDUP - GUTTER
    left = PADDING + LABEL

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g"'
        ' width="%g" height="%g" role="img" aria-label="The Bleep against The'
        ' Fuck, median of %d runs"><title>The Bleep against The Fuck</title>'
        % (WIDTH, height, WIDTH, height, results['runs']),
        '<style>.n{font-family:%s;font-size:12px;font-variant-numeric:'
        'tabular-nums}.x{font-weight:600}.s{font-family:%s;font-size:13.5px}'
        '.k{font-family:%s;font-size:11.5px}</style>' % (MONO, SANS, SANS),
        '<rect width="%g" height="%g" rx="6" fill="%s"/>'
        % (WIDTH, height, ink['card']),
        '<rect x="0.5" y="0.5" width="%g" height="%g" rx="5.5" fill="none"'
        ' stroke="%s"/>' % (WIDTH - 1, height - 1, ink['edge']),
    ]

    # Legend.
    out.append('<rect x="%g" y="20" width="9" height="9" rx="2" fill="%s"'
               ' stroke="%s"/>'
               % (PADDING, ink['fuck'], ink['edge']))
    out.append('<text class="k" x="%g" y="28.5" fill="%s">The Fuck 3.32</text>'
               % (PADDING + 15, ink['dim']))
    out.append('<rect x="%g" y="20" width="9" height="9" rx="2" fill="%s"/>'
               % (PADDING + 112, ink['bleep']))
    out.append('<text class="k" x="%g" y="28.5" fill="%s">The Bleep</text>'
               % (PADDING + 127, ink['label']))
    out.append('<text class="k" x="%g" y="28.5" text-anchor="end" fill="%s">'
               'median of %d runs &#183; each row scaled to The Fuck\'s time'
               ' &#183; lower is better</text>'
               % (WIDTH - PADDING, ink['dim'], results['runs']))
    out.append('<line x1="%g" y1="38.5" x2="%g" y2="38.5" stroke="%s"/>'
               % (PADDING, WIDTH - PADDING, ink['edge']))

    for index, (label, before, after) in enumerate(measured):
        top = HEAD + index * ROW
        middle = top + 13
        share = max(after / before, 0.006)

        out.append('<text class="s" x="%g" y="%g" fill="%s">%s</text>'
                   % (PADDING, middle + BAR + BAR_GAP / 2 - 1, ink['label'],
                      escape(label)))

        # The Fuck: the whole plot, whatever it took.
        out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%g"'
                   ' fill="%s"/>' % (left, middle - BAR, plot, BAR, BAR / 2,
                                     ink['fuck']))
        out.append('<text class="n" x="%g" y="%g" fill="%s">%s</text>'
                   % (left + plot + 10, middle - 0.5, ink['dim'],
                      milliseconds(before)))

        # The Bleep: the same scale.
        width = max(plot * share, 4.0)
        out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%g"'
                   ' fill="%s"/>' % (left, middle + BAR_GAP, width, BAR,
                                     BAR / 2, ink['bleep']))
        out.append('<text class="n" x="%g" y="%g" fill="%s">%s</text>'
                   % (left + width + 10, middle + BAR_GAP + BAR - 0.5,
                      ink['bleep'], milliseconds(after)))

        out.append('<text class="n x" x="%g" y="%g" text-anchor="end"'
                   ' fill="%s">%.1f&#215;</text>'
                   % (WIDTH - PADDING, middle + BAR - 0.5, ink['accent'],
                      before / after))

    out.append('<text class="k" x="%g" y="%g" fill="%s">* dominated by the '
               'half second the command being corrected takes on its own; the'
               ' rest is what the tool costs you.</text>'
               % (PADDING, height - 14, ink['dim']))
    out.append('</svg>\n')
    return '\n'.join(out)


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, os.pardir, 'bench', 'results', 'final.json')
    with open(source) as handle:
        results = json.load(handle)

    for theme in sorted(THEMES):
        name = 'benchmark.svg' if theme == 'light' else 'benchmark-dark.svg'
        path = os.path.join(here, name)
        svg = render(results, theme)
        with open(path, 'w') as handle:
            handle.write(svg)
        print('%s: %d bytes' % (path, len(svg)))


if __name__ == '__main__':
    main(sys.argv)
