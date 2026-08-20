# -*- encoding: utf-8 -*-

"""The corpus: real typos, and whether the answer offered first is the right one.

This is the test the suite did not have. Everything else checks a rule in
isolation against a fixture of its own tool's output, which cannot catch the
thing a user actually meets -- the answer they see comes out of the shared
matching helpers and the ordering across rules, and no rule owns either. That
is how 3,713 green tests coexisted with `whomi` suggesting `which`.

Only the *first* suggestion is asserted, because that is the one enter runs.

Hermetic on purpose: the executables and the history are fixed lists, so this
gives one answer on Linux, macOS and Windows and on a laptop whose history
happens to contain the right thing. See `tests/corpus/README.md`.

"""

import os
import pytest
from thebleep import corrector, utils
from thebleep.types import Command
from tests.corpus import cases

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'corpus')


def _executables():
    with open(os.path.join(CORPUS, 'executables.txt'),
              encoding='utf-8') as handle:
        return [line.strip() for line in handle if line.strip()]


@pytest.fixture(autouse=True, params=[False, True],
                ids=['case-sensitive', 'case-folded'])
def machine(request, mocker, monkeypatch, settings):
    """One machine, the same everywhere: a fixed PATH and a fixed history.

    Run twice, once for each answer to "does this filesystem tell `Git` from
    `git`". Linux says no and Windows and macOS say yes, and the matcher behaves
    differently for each -- so both are exercised on whichever platform the suite
    happens to be running on. A case-folding mistake found by Windows CI twenty
    minutes after a push is the slowest way there is to find one.

    """
    from thebleep import matching

    monkeypatch.setattr(matching, 'FOLD_CASE', request.param)

    names = _executables()

    mocker.patch('thebleep.utils.get_all_executables', return_value=names)
    mocker.patch('thebleep.rules.no_command.get_all_executables',
                 return_value=names)
    mocker.patch('thebleep.utils.get_valid_history_without_current',
                 return_value=cases.HISTORY)
    mocker.patch('thebleep.rules.no_command.get_valid_history_without_current',
                 return_value=cases.HISTORY)

    # `which` decides whether a program exists at all, and the corpus says what
    # exists: the list above, and nothing else.
    installed = set(names)
    # Patched in both places it is reached from: `no_command` imported the name
    # at module load, so patching only `thebleep.utils` would leave the rule
    # asking the real machine.

    def _which(name):
        return ('/usr/bin/' + name
                if os.path.basename(name) in installed else None)

    mocker.patch('thebleep.utils.which', side_effect=_which)
    mocker.patch('thebleep.rules.no_command.which', side_effect=_which)

    monkeypatch.setattr(utils.memoize, 'disabled', True)
    settings.num_close_matches = 3
    return names


def _first(script, output):
    corrected = list(corrector.get_corrected_commands(Command(script, output)))
    return corrected[0].script if corrected else None


def _identify(case):
    return '{} :: {}'.format(case[0], (case[2] or 'nothing'))


@pytest.mark.parametrize('script, output, expect', cases.NO_SUCH_PROGRAM,
                         ids=[_identify(c) for c in cases.NO_SUCH_PROGRAM])
def test_no_such_program(script, output, expect):
    """The busiest path there is, and the only one with no tool to ask."""
    assert _first(script, output) == expect


@pytest.mark.parametrize('script, output, expect', cases.THE_TOOL_SAID_SO,
                         ids=[_identify(c) for c in cases.THE_TOOL_SAID_SO])
def test_the_tool_said_so(script, output, expect):
    """Read rather than guessed, which is why these are the ones that work."""
    assert _first(script, output) == expect


@pytest.mark.parametrize('script, output, expect', cases.NOTHING_IS_RIGHT,
                         ids=[_identify(c) for c in cases.NOTHING_IS_RIGHT])
def test_nothing_is_right(script, output, expect):
    """A confident wrong answer is worse than no answer."""
    assert _first(script, output) == expect


def test_the_corpus_is_worth_running():
    """A guard against the corpus quietly emptying itself.

    It is a data file, and a data file that stops being loaded fails no
    assertions -- so the number of cases is itself asserted.

    """
    assert len(cases.ALL) >= 70
    assert len(_executables()) >= 500
