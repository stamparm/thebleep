# -*- encoding: utf-8 -*-

"""`thebleep.matching`, the measure of how someone mistypes.

The module this replaces was `difflib`, and the reason it was replaced is the
first test here: a transposition has to cost one edit, or `git` and `tic` are
equally good answers for `gti` and the winner is whichever order `PATH` was read
in.

The Windows behaviour is exercised on every platform by setting the flag by
hand. A case-folding bug that only shows up on Windows is a bug found by CI
twenty minutes later, which is the slowest possible way to find one.

"""

import pytest
from thebleep import matching


class TestDistance(object):
    @pytest.mark.parametrize('first, second, expected', [
        # The four ways people mistype, all one edit.
        ('gti', 'git', 1),          # transposition
        ('gt', 'git', 1),           # omission
        ('giit', 'git', 1),         # doubling
        ('gut', 'git', 1),          # neighbouring key
        # And the same word.
        ('git', 'git', 0),
        # Two edits, which is a different word rather than a slip.
        ('gti', 'tic', 2),
        ('whomi', 'which', 3),
    ])
    def test_it_counts_the_mistake(self, first, second, expected):
        assert matching.distance(first, second) == expected

    def test_a_transposition_is_one_edit_and_not_two(self):
        """The whole reason this module exists.

        `difflib` scores `gti` against `git` and against `tic` identically, at
        0.667, because it looks for common subsequences and a swap breaks one.

        """
        assert matching.distance('gti', 'git') == 1
        assert matching.distance('gti', 'tic') > 1

    @pytest.mark.parametrize('first, second', [
        ('', 'git'), ('git', ''), ('', ''),
    ])
    def test_an_empty_name(self, first, second):
        assert matching.distance(first, second) == max(len(first), len(second))

    def test_it_is_symmetric(self):
        for pair in (('gti', 'git'), ('whomi', 'whoami'), ('sl', 'ls')):
            assert matching.distance(*pair) == matching.distance(*pair[::-1])

    @pytest.mark.parametrize('first, second', [
        ('gti', 'git'), ('whomi', 'whoami'), ('whomi', 'which'),
        ('sl', 'ls'), ('nistall', 'uninstall'), ('a', 'zzzzzzzz'),
        ('ssh-keygne', 'ssh-keygen'), ('', 'x'),
    ])
    def test_stopping_early_gives_the_same_answer(self, first, second):
        """`limit` is what makes this affordable over several thousand names,
        and an early exit that returned a different answer would be worse than
        no early exit at all."""
        exact = matching.distance(first, second)
        for limit in range(0, 6):
            bounded = matching.distance(first, second, limit=limit)
            if exact <= limit:
                assert bounded == exact
            else:
                assert bounded > limit


class TestHowFarIsTooFar(object):
    @pytest.mark.parametrize('word, expected', [
        ('ls', 1), ('gti', 1), ('sudp', 1),
        ('whomi', 2), ('docker', 2), ('kubectl', 2), ('apt-get1', 2),
        ('ssh-keygne', 3),
    ])
    def test_roughly_a_quarter_of_the_word(self, word, expected):
        assert matching.max_distance(word) == expected

    @pytest.mark.parametrize('typo, unreachable', [
        # Each of these was offered before, and each is nonsense.
        ('whomi', 'which'),
        ('gti', 'tic'),
        ('wgte', 'getent'),
        ('ping', 'pinky'),
        ('yarn', 'acorn'),
        ('mkae', 'man'),
    ])
    def test_the_absurd_answers_are_out_of_reach(self, typo, unreachable):
        assert matching.rank(typo, [unreachable]) == []

    @pytest.mark.parametrize('typo, wanted', [
        ('whomi', 'whoami'),
        ('gti', 'git'),
        ('sl', 'ls'),
        ('ssh-keygne', 'ssh-keygen'),
        ('kubctl', 'kubectl'),
    ])
    def test_the_intended_answers_are_in_reach(self, typo, wanted):
        assert matching.rank(typo, [wanted]) == [wanted]


class TestOrdering(object):
    def test_distance_decides_first(self):
        assert matching.rank('instal', ['uninstall', 'install'])[0] == 'install'

    def test_the_same_letters_win_a_tie(self):
        """`sl` and `ls` hold the same two letters; `sl` and `sg` do not, and at
        one edit each that is all there is to go on."""
        assert matching.rank('sl', ['sg', 'sh', 'ss', 'ls'])[0] == 'ls'

    def test_a_prefix_wins_next(self):
        """People get the end of a word wrong more often than the start."""
        assert matching.rank('duf', ['df', 'du'])[0] == 'du'

    def test_then_the_longer_shared_opening(self):
        """`sudp` is one edit from both, and `sudo` agrees for three characters
        where `sfdp` agrees for one. The alphabet used to decide, and picked the
        plotting tool."""
        assert matching.rank('sudp', ['sfdp', 'sudo'])[0] == 'sudo'

    def test_the_answer_does_not_depend_on_the_order_asked(self):
        """That arbitrary ordering -- the order `PATH` happened to be read in --
        is what decided `gti` before."""
        candidates = ['tic', 'git', 'gtk', 'gpi', 'gt']
        first = matching.rank('gti', candidates)
        assert matching.rank('gti', list(reversed(candidates))) == first

    def test_a_limit_takes_the_best(self):
        ranked = matching.rank('instal', ['install', 'uninstall', 'inspect'])
        assert matching.rank(
            'instal', ['install', 'uninstall', 'inspect'], limit=1) == \
            ranked[:1]


class TestOrderKeepsEverything:
    """`order` is for a list the failing tool named, `rank` for one we built."""

    def test_nothing_the_tool_said_is_thrown_away(self):
        """kubectl offers `get` and `set` for `gat`; `set` is two edits away and
        `rank` would drop it, but kubectl put it forward and it stays."""
        assert matching.order('gat', ['set', 'get']) == ['get', 'set']
        assert matching.rank('gat', ['set', 'get']) == ['get']

    def test_it_still_puts_the_best_first(self):
        assert matching.order(
            'nistall', ['uninstall', 'install'])[0] == 'install'

    def test_duplicates_are_dropped(self):
        assert matching.order('git', ['git', 'git', 'gti']) == ['git', 'gti']


class TestCaseFolding(object):
    """Windows and macOS do not tell `Git` from `git`.

    Forced both ways here, so the platform the suite happens to run on is not
    what decides whether this is covered.

    """

    @pytest.fixture
    def folding(self, monkeypatch):
        def _set(on):
            monkeypatch.setattr(matching, 'FOLD_CASE', on)

        return _set

    def test_a_capitalised_name_is_still_one_edit_away(self, folding):
        folding(True)
        assert matching.rank('gti', ['Git']) == ['Git']

    def test_and_is_offered_as_it_is_spelled(self, folding):
        folding(True)
        assert matching.order('gat', ['Get', 'Set']) == ['Get', 'Set']

    def test_where_case_matters_it_is_respected(self, folding):
        folding(False)
        # Three edits: two of them the capitals.
        assert matching.rank('gti', ['GIT']) == []
