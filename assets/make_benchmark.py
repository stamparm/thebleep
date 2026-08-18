#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Draws the benchmark chart in the README from the recorded run.

The numbers are read from `bench/results/final.json`, the run committed with
the harness, so the picture cannot drift away from the measurement: regenerate
it after a new run and the chart and the table have to agree.

Bars are scaled against *The Fuck*'s time for the same scenario, so a row
compares the two rather than comparing a shell startup against a megabyte of
build output. Absolute milliseconds are printed on every bar.

Usage: python assets/make_benchmark.py [output.svg]

"""

from __future__ import print_function

import json
import os
import sys

FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'DejaVu Sans Mono', 'Liberation Mono', monospace")
SANS = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, "
        "sans-serif")

WIDTH = 760.0
PADDING = 26.0
LABEL = 208.0            # width of the scenario column
SPEEDUP = 64.0           # width of the speedup column
GUTTER = 74.0            # room after the longest bar for its own figure
BAR = 11.0               # bar thickness
BAR_GAP = 5.0
ROW = 58.0
HEAD = 52.0
FOOT = 34.0

INK = {
    'card': '#15181f',
    'edge': '#2b313c',
    'label': '#c3cad4',
    'dim': '#7d8794',
    'fuck': '#565f70',
    'bleep': '#5fd38d',
    'accent': '#ffb454',
    'on_bar': '#0f1218',
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
        '<style>.m{font-family:%s;font-size:12.5px}.s{font-family:%s;'
        'font-size:13px}.k{font-family:%s;font-size:11.5px}</style>'
        % (FONT, SANS, SANS),
        '<rect width="%g" height="%g" rx="10" fill="%s"/>'
        % (WIDTH, height, INK['card']),
        '<rect x="0.5" y="0.5" width="%g" height="%g" rx="9.5" fill="none"'
        ' stroke="%s"/>' % (WIDTH - 1, height - 1, INK['edge']),
    ]

    # Legend.
    out.append('<rect x="%g" y="21" width="10" height="10" rx="3" fill="%s"/>'
               % (PADDING, INK['fuck']))
    out.append('<text class="k" x="%g" y="30" fill="%s">The Fuck 3.32</text>'
               % (PADDING + 16, INK['dim']))
    out.append('<rect x="%g" y="21" width="10" height="10" rx="3" fill="%s"/>'
               % (PADDING + 116, INK['bleep']))
    out.append('<text class="k" x="%g" y="30" fill="%s">The Bleep</text>'
               % (PADDING + 132, INK['label']))
    out.append('<text class="k" x="%g" y="30" text-anchor="end" fill="%s">'
               'median of %d runs &#183; each row scaled to The Fuck\'s time'
               ' &#183; lower is better</text>'
               % (WIDTH - PADDING, INK['dim'], results['runs']))

    for index, (label, before, after) in enumerate(measured):
        top = HEAD + index * ROW
        middle = top + 14
        share = max(after / before, 0.006)

        out.append('<text class="s" x="%g" y="%g" fill="%s">%s</text>'
                   % (PADDING, middle + BAR + BAR_GAP / 2, INK['label'],
                      escape(label)))

        # The Fuck: the whole plot, whatever it took.
        out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%g"'
                   ' fill="%s"/>' % (left, middle - BAR, plot, BAR, BAR / 2,
                                     INK['fuck']))
        out.append('<text class="m" x="%g" y="%g" fill="%s">%s</text>'
                   % (left + plot + 9, middle - 1.5, INK['dim'],
                      milliseconds(before)))

        # The Bleep: the same scale.
        width = max(plot * share, 5.0)
        out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%g"'
                   ' fill="%s"/>' % (left, middle + BAR_GAP, width, BAR,
                                     BAR / 2, INK['bleep']))
        out.append('<text class="m" x="%g" y="%g" fill="%s">%s</text>'
                   % (left + width + 9, middle + BAR_GAP + BAR - 1.5,
                      INK['bleep'], milliseconds(after)))

        out.append('<text class="m" x="%g" y="%g" text-anchor="end"'
                   ' fill="%s">%.1f×</text>'
                   % (WIDTH - PADDING, middle + BAR - 1, INK['accent'],
                      before / after))

    out.append('<text class="k" x="%g" y="%g" fill="%s">* dominated by the '
               'half second the command being corrected takes on its own; the'
               ' rest is what the tool costs you.</text>'
               % (PADDING, height - 15, INK['dim']))
    out.append('</svg>\n')
    return '\n'.join(out)


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, os.pardir, 'bench', 'results', 'final.json')
    with open(source) as handle:
        results = json.load(handle)

    svg = render(results)
    path = argv[1] if len(argv) > 1 else 'assets/benchmark.svg'
    with open(path, 'w') as handle:
        handle.write(svg)
    print('%s: %d bytes from %s' % (path, len(svg), source))


if __name__ == '__main__':
    main(sys.argv)
