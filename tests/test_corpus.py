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
from thebleep import corrector, matching, utils
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
    mocker.patch(
        'thebleep.rules.missing_space_before_subcommand.get_all_executables',
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

    _stub_the_tools(mocker, settings)

    monkeypatch.setattr(utils.memoize, 'disabled', True)
    settings.num_close_matches = 3
    return names


# What `npm run-script` lists. Captured from npm 10.8.2.
NPM_SCRIPTS = ['build', 'test', 'start', 'watch']


def _stub_the_tools(mocker, settings):
    """Answer for the tools instead of running them -- where that is possible.

    There is a trap here that cost two red CI runs, and it is worth knowing
    before adding a case. The corrector does not use the rule modules you can
    `import`: `thebleep.rulepack` loads each rule from its source file, so the
    module object it runs is a different one. Patching a helper *defined inside
    a rule* therefore does nothing, while patching one in a module the rule
    imports works perfectly -- because the freshly loaded rule does its import
    after the patch is in place.

    So `thebleep.utils.get_all_executables` and `thebleep.specific.npm` can be
    answered for, and `apt_invalid_operation._get_operations` cannot. Cases that
    need the second kind are not in the corpus at all; they live in that rule's
    own tests, which call `get_new_command` directly and can patch it. What is
    here is the path that matters most anyway -- the guess with no tool to ask --
    plus the rules that read the answer out of output and run nothing.

    Rules gated on a tool being installed are named explicitly in
    `settings.rules`, which `Rule.is_enabled` honours ahead of
    `enabled_by_default`. Without that, npm's rules are simply off on a runner
    with no npm and answer nothing.

    """
    from thebleep import const

    settings.rules = [const.ALL_ENABLED, 'npm_missing_script',
                      'npm_wrong_command']

    mocker.patch('thebleep.specific.npm.get_scripts', return_value=NPM_SCRIPTS)
    mocker.patch('thebleep.specific.npm.get_all_scripts',
                 return_value=NPM_SCRIPTS)


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


# The commands a developer types most, restricted to ones the snapshot has.
COMMONEST = [
    'git', 'ls', 'cd', 'grep', 'cat', 'python3', 'pip', 'npm', 'node',
    'docker', 'kubectl', 'ssh', 'curl', 'tar', 'mkdir', 'touch', 'chmod',
    'sudo', 'apt', 'vim', 'cargo', 'rm', 'mv', 'cp', 'find', 'sort', 'head',
    'tail', 'echo', 'kill', 'ps', 'df', 'du',
]


def _single_edit_typos(word, known):
    """Every one-slip misspelling of `word` that is not itself a command."""
    out = set()
    for index in range(len(word) - 1):
        out.add(word[:index] + word[index + 1] + word[index]
                + word[index + 2:])                      # transposition
    for index in range(len(word)):
        out.add(word[:index] + word[index + 1:])          # omission
        out.add(word[:index] + word[index] + word[index:])  # doubling

    return {typo for typo in out
            if len(typo) > 1 and typo not in known}


def test_every_single_slip_in_a_common_command_is_corrected(machine):
    """Generated rather than imagined, which is the point.

    A hand-written list of typos is a list of the ones somebody thought of. This
    makes every transposition, omission and doubled letter of the commands a
    developer types most -- a few hundred cases -- and requires that the answer
    is the command they came from, or something no further away.

    Nothing absurd and nothing silent: the two ways this used to fail were
    offering `tic` for `gti` (further away, and it won on a tie) and offering
    nothing at all because the metric could not see a transposition.

    """
    known = set(machine)
    absurd = []
    silent = []

    for command in COMMONEST:
        if command not in known:
            continue
        for typo in sorted(_single_edit_typos(command, known)):
            ranked = matching.rank(typo, machine, limit=1)
            if not ranked:
                silent.append((typo, command))
            elif ranked[0] != command and (
                    matching.distance(typo, ranked[0])
                    > matching.distance(typo, command)):
                absurd.append((typo, command, ranked[0]))

    assert not absurd, 'a further-away command won: {}'.format(absurd[:10])
    assert not silent, 'no suggestion at all for: {}'.format(silent[:10])
