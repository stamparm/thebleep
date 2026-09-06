#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Writes the playground's data file from the corpus.

The page at `docs/index.html` runs the real package in the browser, but a
WebAssembly interpreter and a wheel take a few seconds to arrive, and a page
with nothing on it is a page people leave. So every corpus case is answered
here, ahead of time, and `docs/cases.json` is what the page draws at first
paint; the browser's own copy of the engine takes over for whatever the visitor
types themselves.

The cases are `tests/corpus/cases.py` unchanged -- typos a person really makes,
each `output` captured by running the failing command, each `expect` argued over
in review. Nothing here is written by hand, and that is the point: a demo whose
examples were invented is a demo that can be wrong in the direction that
flatters it.

Usage:

    python assets/make_playground.py

`--check` writes nothing and fails if the committed file is not what the engine
says today, which is what `tests/test_playground.py` runs.

    python assets/make_playground.py --check

"""

from __future__ import print_function

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
CORPUS = os.path.join(ROOT, 'tests', 'corpus')
TARGET = os.path.join(DOCS, 'cases.json')

sys.path.insert(0, DOCS)
sys.path.insert(0, ROOT)

import bootstrap                    # noqa: E402  (needs DOCS on the path)
from tests.corpus import cases      # noqa: E402  (needs ROOT on the path)

# The corpus's own three groups, and what each is here to show. The third is
# the one a demo would normally leave out, and the one most worth keeping.
GROUPS = [
    ('No such program',
     'The commonest way a command fails, and the only one with no tool to ask'
     ' -- every answer here is a guess. It is made against a fixed PATH and a'
     ' fixed history, so what you see is what I see.',
     cases.NO_SUCH_PROGRAM),
    ('The tool said so',
     'Read rather than guessed. The failing tool printed something the engine'
     ' can point at, which is why these are the ones that work.',
     cases.THE_TOOL_SAID_SO),
    ('Nothing is right',
     'Cases where saying nothing is the answer. A confident wrong answer is'
     ' worse than no answer, and several of these were wrong answers once.',
     cases.NOTHING_IS_RIGHT),
]


def _executables():
    with io.open(os.path.join(CORPUS, 'executables.txt'),
                 encoding='utf-8') as handle:
        return [line.strip() for line in handle if line.strip()]


def build():
    executables = _executables()
    bootstrap.install(executables, cases.HISTORY)

    groups = []
    for name, note, group in GROUPS:
        answered = []
        for script, output, expect in group:
            result = bootstrap.answer(script, output)
            answered.append({'script': script,
                             'output': output,
                             'expect': expect,
                             'decision': result['decision'],
                             'suggestions': result['suggestions']})
        groups.append({'name': name, 'note': note, 'cases': answered})

    # No version in here on purpose. The page learns which wheel to install
    # from `wheel.json`, which the deploy workflow writes beside the wheel it
    # just built -- so opening the next version does not leave this file stale
    # and the release red, which is a way this repository has been bitten
    # before by exactly one string too many being coupled to `setup.py`.
    return {'source': 'tests/corpus/cases.py',
            'executables': executables,
            'history': list(cases.HISTORY),
            'groups': groups}


def render(data):
    """Sorted keys and a trailing newline, so a regenerated file diffs small."""
    return json.dumps(data, indent=1, sort_keys=True,
                      ensure_ascii=False) + '\n'


def main(argv):
    check_only = '--check' in argv[1:]
    rendered = render(build())

    if check_only:
        try:
            with io.open(TARGET, encoding='utf-8') as handle:
                committed = handle.read()
        except IOError:
            sys.exit('make_playground.py: docs/cases.json is missing;'
                     ' run python assets/make_playground.py')
        if committed != rendered:
            sys.exit('make_playground.py: docs/cases.json is not what the'
                     ' engine says today; run python'
                     ' assets/make_playground.py')
        return

    # `newline=''` so regenerating on Windows does not rewrite every line of a
    # committed file with a carriage return on the end of it.
    with io.open(TARGET, 'w', encoding='utf-8', newline='') as handle:
        handle.write(rendered)
    print('wrote %s' % os.path.relpath(TARGET, ROOT))


if __name__ == '__main__':
    main(sys.argv)
