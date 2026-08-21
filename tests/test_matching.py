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
        # Nine to twelve characters used to get 3, which is a third of a
        # nine-letter word rather than a quarter -- and it showed:
        # `systemctl statu ssh` was answered with `sysctl statu ssh`.
        ('systemctl', 2), ('ssh-keygne', 2), ('docker-compo', 2),
        ('docker-compose', 3),
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
        # A container without systemd. Three edits in a nine-letter name.
        ('systemctl', 'sysctl'),
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


def test_rank_offers_no_candidate_twice():
    """A name can arrive twice: `option_typo` reads a program's options out of
    the printed usage *and* out of `--help`, and `--color` is in both -- so two
    of the three suggestions were the same string. `order` deduplicated
    already; `rank` did not."""
    ranked = matching.rank('colour', ['color', 'color', 'column', 'color'])
    assert ranked == sorted(set(ranked), key=ranked.index)
    assert ranked.count('color') == 1


class TestWhereTheKeysAre:
    """`a` mistyped as `d` is not as likely as `ca` missing its last letter.

    Damerau-Levenshtein charges one edit for either, which is what let `cd`
    stand beside `cat` as an equally good answer for `ca`.

    """

    def test_a_neighbour_is_one_key_away(self):
        assert matching.key_distance('a', 's') == 1.0
        assert matching.key_distance('o', 'i') == 1.0

    def test_the_diagonals_count_as_neighbours(self):
        assert matching.key_distance('a', 'q') <= matching.ADJACENT
        assert matching.key_distance('s', 'w') <= matching.ADJACENT
        assert matching.key_distance('a', 'z') <= matching.ADJACENT

    def test_two_columns_over_is_not_a_slip(self):
        assert matching.key_distance('a', 'd') == 2.0
        assert matching.key_distance('a', 'd') > matching.ADJACENT

    def test_the_same_physical_key_on_qwertz(self):
        """`y` and `z` swap between QWERTY and QWERTZ, so a German-layout slip
        lands on the other one. Straight-line distance on a QWERTY grid puts
        them five keys apart."""
        assert matching.key_distance('y', 'z') <= matching.ADJACENT

    def test_a_character_off_the_grid_is_not_called_a_slip(self):
        assert matching.key_distance('a', u'\u00e9') > matching.ADJACENT

    def test_a_missed_key_is_explained_and_a_far_reach_is_not(self):
        assert matching.plausible('ca', 'cat')
        assert matching.plausible('ca', 'cs')
        assert not matching.plausible('ca', 'cd')

    def test_a_transposition_is_not_read_as_two_bad_reaches(self):
        """`sl` and `ls` differ in both positions, which position-by-position
        looks like two expensive substitutions when it is one swap."""
        assert matching.plausible('sl', 'ls')

    def test_the_adjacent_slip_wins_the_tie(self):
        """Nothing else separates them: same distance, neither is a prefix,
        both share one opening character. Left to the alphabet, `cd` won."""
        assert matching.rank('ca', ['cd', 'cs']) == ['cs', 'cd']

    def test_the_shared_opening_still_outranks_the_reach(self):
        """`order` keeps every candidate, so once distances hit the cap the
        shared opening carries the decision. A reach term above it promoted
        long unrelated words -- `extension` over `none` for `nmae`."""
        assert matching.order('nmae', ['none', 'extension'])[0] == 'none'


class TestWhatOutsideEvidenceMayReorder:

    def test_a_two_key_jump_is_not_up_for_reordering(self):
        """The whole `ca` case: `cat` and `cd` are both one edit away, and only
        one of them is a plausible slip."""
        ranked = matching.rank_with_distance('ca', ['cat', 'cd', 'cs'])
        assert matching.plausible_slips('ca', ranked) == ['cat', 'cs']

    def test_an_adjacent_slip_is(self):
        """`got` is one key from `git` and one dropped key from `go`, so both
        are real explanations and history is the right thing to choose with."""
        ranked = matching.rank_with_distance('got', ['go', 'git'])
        assert sorted(matching.plausible_slips('got', ranked)) == ['git', 'go']

    def test_nothing_further_away_than_the_closest(self):
        """`gtk` stays: `i` and `k` are neighbours, so it is a real explanation
        even though `git` is the better one. `grep` is three edits away and is
        not up for reordering at any price."""
        ranked = matching.rank_with_distance('gti', ['git', 'gtk', 'grep'])
        slips = matching.plausible_slips('gti', ranked)
        assert 'grep' not in slips
        assert slips[0] == 'git'

    def test_no_candidates_at_all(self):
        assert matching.plausible_slips('ca', []) == []
