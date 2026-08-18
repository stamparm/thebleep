#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Draws the benchmark chart in the README from the recorded run.

The numbers are read from `bench/results/final.json`, the run committed with
the harness, so the picture cannot drift away from the measurement: regenerate
it after a new run and the chart and the table have to agree.

Bars are scaled against *The Fuck*'s time for the same scenario, so a row
compares the two rather than comparing a shell startup against a megabyte of
build output. Absolute milliseconds are printed beside every bar.

One file, which carries both themes: the colours are CSS variables, and a
`prefers-color-scheme` query swaps them. That is one asset to keep in sync
instead of two, it needs no `<picture>` element and no absolute URL, and where
the query is not honoured the reader gets the light chart -- which has its own
white card, so it stays legible on a dark page anyway.

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


def palette():
    """The colours as CSS variables, light by default and dark on request."""
    def variables(theme):
        return ''.join('--%s:%s;' % (name, colour)
                       for name, colour in sorted(THEMES[theme].items()))

    return (':root{%s}'
            '@media(prefers-color-scheme:dark){:root{%s}}'
            % (variables('light'), variables('dark')))


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


def render(results):
    measured = list(rows(results))
    height = HEAD + len(measured) * ROW + FOOT
    plot = WIDTH - PADDING * 2 - LABEL - SPEEDUP - GUTTER
    left = PADDING + LABEL

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g"'
        ' width="%g" height="%g" role="img" aria-label="The Bleep against The'
        ' Fuck, median of %d runs"><title>The Bleep against The Fuck</title>'
        % (WIDTH, height, WIDTH, height, results['runs']),
        '<style>%s.n{font-family:%s;font-size:12px;font-variant-numeric:'
        'tabular-nums}.x{font-weight:600}.s{font-family:%s;font-size:13.5px}'
        '.k{font-family:%s;font-size:11.5px}'
        '.card{fill:var(--card)}.edge{fill:none;stroke:var(--edge)}'
        '.rule{stroke:var(--edge)}.label{fill:var(--label)}'
        '.dim{fill:var(--dim)}.fuck{fill:var(--fuck)}'
        '.swatch{fill:var(--fuck);stroke:var(--edge)}'
        '.bleep{fill:var(--bleep)}.accent{fill:var(--accent)}</style>'
        % (palette(), MONO, SANS, SANS),
        '<rect class="card" width="%g" height="%g" rx="6"/>'
        % (WIDTH, height),
        '<rect class="edge" x="0.5" y="0.5" width="%g" height="%g" rx="5.5"/>'
        % (WIDTH - 1, height - 1),
    ]

    # Legend.
    out.append('<rect class="swatch" x="%g" y="20" width="9" height="9"'
               ' rx="2"/>' % PADDING)
    out.append('<text class="k dim" x="%g" y="28.5">The Fuck 3.32</text>'
               % (PADDING + 15))
    out.append('<rect class="bleep" x="%g" y="20" width="9" height="9"'
               ' rx="2"/>' % (PADDING + 112))
    out.append('<text class="k label" x="%g" y="28.5">The Bleep</text>'
               % (PADDING + 127))
    out.append('<text class="k dim" x="%g" y="28.5" text-anchor="end">'
               'median of %d runs &#183; each row scaled to The Fuck\'s time'
               ' &#183; lower is better</text>'
               % (WIDTH - PADDING, results['runs']))
    out.append('<line class="rule" x1="%g" y1="38.5" x2="%g" y2="38.5"/>'
               % (PADDING, WIDTH - PADDING))

    for index, (label, before, after) in enumerate(measured):
        top = HEAD + index * ROW
        middle = top + 13
        share = max(after / before, 0.006)

        out.append('<text class="s label" x="%g" y="%g">%s</text>'
                   % (PADDING, middle + BAR + BAR_GAP / 2 - 1, escape(label)))

        # The Fuck: the whole plot, whatever it took.
        out.append('<rect class="fuck" x="%g" y="%g" width="%g" height="%g"'
                   ' rx="%g"/>' % (left, middle - BAR, plot, BAR, BAR / 2))
        out.append('<text class="n dim" x="%g" y="%g">%s</text>'
                   % (left + plot + 10, middle - 0.5, milliseconds(before)))

        # The Bleep: the same scale.
        width = max(plot * share, 4.0)
        out.append('<rect class="bleep" x="%g" y="%g" width="%g" height="%g"'
                   ' rx="%g"/>'
                   % (left, middle + BAR_GAP, width, BAR, BAR / 2))
        out.append('<text class="n bleep" x="%g" y="%g">%s</text>'
                   % (left + width + 10, middle + BAR_GAP + BAR - 0.5,
                      milliseconds(after)))

        out.append('<text class="n x accent" x="%g" y="%g" text-anchor="end">'
                   '%.1f&#215;</text>'
                   % (WIDTH - PADDING, middle + BAR - 0.5, before / after))

    out.append('<text class="k dim" x="%g" y="%g">* dominated by the half '
               'second the command being corrected takes on its own; the rest'
               ' is what the tool costs you.</text>'
               % (PADDING, height - 14))
    out.append('</svg>\n')
    return '\n'.join(out)


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, os.pardir, 'bench', 'results', 'final.json')
    with open(source) as handle:
        results = json.load(handle)

    path = os.path.join(here, 'benchmark.svg')
    svg = render(results)
    with open(path, 'w') as handle:
        handle.write(svg)
    print('%s: %d bytes' % (path, len(svg)))


if __name__ == '__main__':
    main(sys.argv)
