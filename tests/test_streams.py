# -*- coding: utf-8 -*-

import io
import sys
from thebleep.system.streams import use_utf8


class _NotAStream(object):
    """Something a test runner or colorama put where a stream used to be."""


def test_use_utf8_sets_the_encoding(monkeypatch):
    """A rule quoting `Résumé.pdf` back must not depend on the locale.

    An ASCII stream is what an interpreter started under the C locale with
    UTF-8 mode off actually gets, and writing a file name through it raises.

    """
    ascii_out = io.TextIOWrapper(io.BytesIO(), encoding='ascii')
    monkeypatch.setattr(sys, 'stdout', ascii_out)
    monkeypatch.setattr(sys, 'stderr', ascii_out)

    use_utf8()

    assert ascii_out.encoding == 'utf-8'
    ascii_out.write(u'Résumé.pdf')


def test_use_utf8_leaves_alone_what_it_cannot_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, 'stdout', _NotAStream())
    monkeypatch.setattr(sys, 'stderr', _NotAStream())
    use_utf8()


def test_use_utf8_survives_a_closed_stream(monkeypatch):
    closed = io.TextIOWrapper(io.BytesIO(), encoding='ascii')
    closed.close()
    monkeypatch.setattr(sys, 'stdout', closed)
    monkeypatch.setattr(sys, 'stderr', closed)
    use_utf8()
