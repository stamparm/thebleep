#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Writes the README's benchmark chart from the recorded run.

The chart is text in a fenced block rather than a picture: it is readable in
the markdown itself, on GitHub, on PyPI and in a terminal, it needs no asset
to keep in sync, and it says everything a table would have said, so there is
no table beside it repeating the numbers.

Each bar is The Bleep's time as a share of The Fuck's for the same scenario --
what is left of the bar is what the row costs now -- so a row compares the two
rather than comparing a shell startup against a megabyte of build output. The
absolute milliseconds are on every row.

Run it after recording a new run and the README is rewritten in place:

    python bench/chart.py

"""

from __future__ import print_function

import io
import json
import os
import sys

# One eighth of a cell at a time, so the short bars are still drawn to scale
# rather than rounded away to nothing. The track behind the bar is a shade
# rather than a dotted line: both are Block Elements, so they keep the same
# advance width as the fill in any monospace font, and being text they take
# the colours of whichever theme the reader is on.
EIGHTHS = u' ▏▎▍▌▋▊▉'
FULL = u'█'
EMPTY = u'░'
CELLS = 18

BEGIN = u'<!-- benchmark: written by bench/chart.py -->'
END = u'<!-- end benchmark -->'

# The scenarios worth showing, in the order they are worth reading, with the
# names the harness gives them. `version` is left out as a second measurement
# of the same startup cost as `alias`.
SCENARIOS = [
    ('alias', u'Open a shell'),
    ('correct-fast', u'Correct a mistyped command'),
    ('correct-in-repo', u'Correct inside a git repository'),
    ('correct-nomatch', u'Correct when nothing matches'),
    ('correct-slow', u'Correct a slow command *'),
    ('correct-big-output', u'Correct after 1 MB of output'),
]


def milliseconds(value):
    if value >= 1000:
        return u'%.2f s' % (value / 1000.0)
    if value >= 10:
        return u'%d ms' % round(value)
    return u'%.1f ms' % value


def bar(share):
    """A bar `CELLS` wide, filled to `share` of its width."""
    filled = max(share, 0.0) * CELLS
    whole = int(filled)
    part = int(round((filled - whole) * 8))
    if part == 8:
        whole, part = whole + 1, 0
    drawn = FULL * whole + (EIGHTHS[part] if part else u'')
    if not drawn:
        drawn = EIGHTHS[1]
    return drawn + EMPTY * (CELLS - len(drawn))


def rows(results):
    subjects = results['subjects']
    for name, label in SCENARIOS:
        before = subjects['fuck']['scenarios'].get(name)
        after = subjects['bleep']['scenarios'].get(name)
        if before and after:
            yield label, before['median'], after['median']


HEADINGS = (u'% of The Fuck\'s time', u'The Fuck', u'The Bleep', u'faster')


def chart(results):
    measured = list(rows(results))

    def column(heading, values):
        return max([len(heading)] + [len(value) for value in values])

    bars, before, after, faster = HEADINGS
    label_width = max(len(label) for label, _, _ in measured)
    before_width = column(before, [milliseconds(b) for _, b, _ in measured])
    after_width = column(after, [milliseconds(a) for _, _, a in measured])
    faster_width = column(faster, [u'%.1f×' % (b / a)
                                   for _, b, a in measured])

    # The bar's heading is right-aligned to the end of the bars, so a heading
    # wider than the bars themselves reaches back over the blank space above
    # the scenario names rather than pushing the columns to its right out of
    # line with the figures underneath them.
    lines = [u'%s  %s  %s  %s' % (bars.rjust(label_width + 2 + CELLS),
                                  before.rjust(before_width),
                                  after.rjust(after_width),
                                  faster.rjust(faster_width))]
    for label, time_before, time_after in measured:
        lines.append(u'%s  %s  %s  %s  %s' % (
            label.ljust(label_width),
            bar(time_after / time_before),
            milliseconds(time_before).rjust(before_width),
            milliseconds(time_after).rjust(after_width),
            (u'%.1f×' % (time_before / time_after)).rjust(faster_width)))
    return u'\n'.join(lines)


def block(results):
    return u'\n'.join([BEGIN, u'```text', chart(results), u'```', END])


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    with io.open(os.path.join(here, 'results', 'final.json'),
                 encoding='utf-8') as handle:
        results = json.load(handle)

    replacement = block(results)
    print(replacement)

    readme = os.path.join(here, os.pardir, 'README.md')
    with io.open(readme, encoding='utf-8') as handle:
        text = handle.read()

    if BEGIN not in text or END not in text:
        sys.exit('chart.py: no benchmark block in README.md to replace')

    start = text.index(BEGIN)
    finish = text.index(END) + len(END)
    updated = text[:start] + replacement + text[finish:]

    if updated == text:
        print('\nREADME.md is already up to date.')
        return

    with io.open(readme, 'w', encoding='utf-8') as handle:
        handle.write(updated)
    print('\nREADME.md updated.')


if __name__ == '__main__':
    main(sys.argv)
