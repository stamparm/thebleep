# -*- encoding: utf-8 -*-

"""What did you mean -- the question the whole tool exists to answer.

There was no module for this. The answer came out of three utility functions
inherited unexamined from The Fuck, and the metric underneath them was
`difflib.SequenceMatcher`, which measures *similarity of sequences* and was
being asked to measure *how someone mistypes*. Those are not the same thing, and
the difference is not academic:

    difflib ratio        gti/git 0.667   gti/tic 0.667   gti/gtk 0.667

A four-way tie, so the answer fell to whichever order `PATH` happened to be
scanned in -- which is why `gti status` suggested `tic status`, the terminfo
compiler. `git` earned no credit for being one *swap* away, because
`SequenceMatcher` finds common subsequences and has no idea what a transposition
is.

Typing mistakes have a shape. Nearly all of them are one of four things: two
letters swapped, one letter left out, one letter doubled or added, one letter
hit instead of its neighbour. Damerau-Levenshtein distance counts exactly those
-- a transposition is one edit, not two -- so the same comparison becomes:

    edit distance        gti/git 1       gti/tic 2       gti/gtk 2

and the tie is gone. Measured across the corpus, every intended command is one
or two edits away and nearly every absurd suggestion is three or more; that gap
is what this module is for. See `tests/corpus/`.

"""

import os

# Windows and macOS do not distinguish `Git` from `git`, so neither may this:
# comparing case-sensitively there makes a capitalised name on `PATH` look two
# edits further away than it is. Compared folded, offered as spelled -- which is
# what the `difflib` wrapper this replaces did, and dropping it would have been a
# Windows-only regression nothing else would catch.
FOLD_CASE = os.path.normcase('A') == os.path.normcase('a')


def _fold(name):
    return name.lower() if FOLD_CASE else name


def max_distance(word):
    """The furthest a candidate may be and still be worth offering.

    Roughly a quarter of the word, measured against the corpus rather than
    picked. The boundaries all earn their place: `gti` must not reach `tic` (two edits), `whomi` must not reach
    `which` (three), and `mkae` must not reach `man` -- two edits in a
    four-letter word is not a slip, it is a different word, and on a machine
    without `make` installed the honest answer is nothing at all.

    This used to be written out as three cases, and the last of them said 3 for
    everything longer than eight characters -- which for a nine-letter word is a
    third of it, not a quarter, and it showed:

        $ systemctl statu ssh        # in a container with no systemd
        $ bleep
        sysctl statu ssh             <- three edits, and nonsense

    A quarter of nine is two, which excludes it -- so the tier that said 3 now
    starts where a third really is a quarter.

    The arithmetic is not written as `len(word) // 4` because that also tightens
    the middle: `kubectl` is seven characters, a quarter of which is one, and
    two edits in a seven-letter name is a slip somebody really makes. The tiers
    are what the corpus was measured against; only the top one moved.

    The cost is that a doubly-mangled short name cannot be reached: `ndeo` is
    two edits from `node` and gets no suggestion. That is the trade, and it is
    the right way round -- a wrong answer offered confidently is worse than
    none, and single-slip typos are the overwhelming majority.

    """
    length = len(word)
    if length <= 4:
        return 1
    if length <= 12:
        return 2
    return 3


def distance(first, second, limit=None):
    """Damerau-Levenshtein distance between two names.

    Counts a transposition as one edit, which is the whole point: `gti` is one
    mistake away from `git`, and any measure that calls it two puts `tic`
    alongside it.

    `limit` stops early. This is asked of every executable on the machine --
    several thousand on a developer's box -- so the common case has to be a
    cheap "no": one row of the matrix is enough to know the answer is already
    over the limit.

    """
    if first == second:
        return 0

    # A length difference is already that many edits, so most candidates are
    # refused before any work happens.
    if limit is not None and abs(len(first) - len(second)) > limit:
        return limit + 1

    if not first:
        return len(second)
    if not second:
        return len(first)

    previous = None
    current = list(range(len(second) + 1))

    for i, first_char in enumerate(first):
        before, previous, current = previous, current, [i + 1] + [0] * len(
            second)

        for j, second_char in enumerate(second):
            cost = 0 if first_char == second_char else 1
            current[j + 1] = min(
                previous[j + 1] + 1,        # deletion
                current[j] + 1,             # insertion
                previous[j] + cost,         # substitution
            )
            # Transposition: the two characters are the same pair, swapped.
            if (i and j and first_char == second[j - 1]
                    and first[i - 1] == second_char):
                current[j + 1] = min(current[j + 1], before[j - 1] + 1)

        if limit is not None and min(current) > limit:
            return limit + 1

    return current[-1]


# --------------------------------------------------------------------------
# where the keys are
#
# The docstring above lists "one letter hit instead of its neighbour" as one of
# the four shapes a typing mistake comes in, and then nothing here knew where
# any key was. Damerau-Levenshtein charges one edit for a substitution wherever
# the two letters live, so `ca` was one edit from `cat` *and* one edit from `cd`
# -- and `a` and `d` are two keys apart, hit by different fingers. A slip is a
# neighbour; anything further is somebody typing a different word.
#
# QWERTZ is QWERTY with `y` and `z` exchanged, and those two are handled as
# neighbours of each other for exactly that reason: a German-layout user's slip
# lands on the other one. No other key moves between the two layouts, so one
# grid serves both -- which covers most of the world's keyboards and is why
# there is no setting here to get wrong.
# --------------------------------------------------------------------------

# Column offsets are the real stagger of a physical row, not a grid: `a` sits a
# quarter-key right of `q`, `z` half a key right of `a`. Straight columns would
# make `q` and `a` the same distance apart as `q` and `w`.
_ROWS = (
    (0.00, '1234567890-='),
    (0.50, 'qwertyuiop[]'),
    (0.75, "asdfghjkl;'"),
    (1.25, 'zxcvbnm,./'),
)

# Far enough to be "not a slip", for a character that is not on the grid at all.
_OFF_GRID = 6.0

_KEYS = {char: (row_index, offset + column)
         for row_index, (offset, row) in enumerate(_ROWS)
         for column, char in enumerate(row)}

# The same grid, with `y` and `z` sitting in each other's slot. QWERTZ does not
# just swap the two letters' meaning for each other -- it moves `z` into the
# slot next to `t` and `u`, and `y` into the slot next to `a` and `x`. A slip
# that lands on one of *those* neighbours is invisible if the only concession
# made is "`y` and `z` are the same key": `zmux` for `tmux` is `z` hit for its
# QWERTZ neighbour `t`, not `z` hit for `y`.
_KEYS_QWERTZ = dict(_KEYS, y=_KEYS['z'], z=_KEYS['y'])


def _grid_distance(first, second, keys):
    here, there = keys.get(first), keys.get(second)
    if here is None or there is None:
        return _OFF_GRID
    return ((here[0] - there[0]) ** 2 + (here[1] - there[1]) ** 2) ** 0.5


def key_distance(first, second):
    """How far apart two characters sit on the keyboard.

    Adjacent keys are 1.0 apart, `a` to `d` is 2.0, and anything not on the
    grid -- a digit in one name and a letter in the other, a non-Latin
    character -- is `_OFF_GRID`, because we cannot say it was a slip.

    Which physical key typed `y` or `z` depends on a layout nobody here is
    told, so both readings are tried and the more charitable one wins -- the
    same reasoning `FOLD_CASE` already applies to case.

    """
    if first == second:
        return 0.0
    if {first, second} == {'y', 'z'}:
        # the same physical key on QWERTY and QWERTZ
        return 1.0
    return min(_grid_distance(first, second, _KEYS),
               _grid_distance(first, second, _KEYS_QWERTZ))


def _misreach(word, candidate):
    """Total keyboard distance of the substitutions this candidate implies.

    Only for two names of the same length, which is the case a substitution
    explains; a name one character longer was reached by leaving a key out or
    adding one, and where the keys sit says nothing about that.

    Transpositions are skipped for the same reason. `sl` and `ls` differ in both
    positions, so position-by-position this looks like two expensive
    substitutions when it is one swap -- and the `anagram` term above already
    puts it where it belongs.

    """
    if len(word) != len(candidate) or sorted(word) == sorted(candidate):
        return 0.0
    return round(sum(key_distance(first, second)
                     for first, second in zip(word, candidate)
                     if first != second), 2)


def _key(word, candidate):
    """How good a candidate is, best first when sorted ascending.

    Distance decides. Ties are broken by four things, in order:

    - the same letters in a different order wins -- a transposition, which is
      the commonest slip there is. `sl` and `ls` hold the same two letters;
      `sl` and `sg` do not, and at one edit each that is the only thing telling
      them apart.
    - then a candidate the typo is a prefix of, or that is a prefix of the
      typo. People get the end of a word wrong far more often than the start,
      so `duf` is `du` before it is `df`.
    - then the longer shared opening. `sudp` is one edit from both `sudo` and
      `sfdp`; the first agrees for three characters and the second for one, and
      people mistype the ends of words far more often than the beginnings. Left
      to the alphabet, `sfdp` won.
    - then the name itself, so the answer never depends on the order `PATH` was
      read in. That arbitrary ordering is what decided `gti` before.

    """
    return _key_from(word, candidate,
                     distance(word, candidate, limit=max_distance(word)))


# A neighbouring key, including the diagonals: `a`/`w` are 1.25 apart on the
# grid above, `a`/`d` are 2.0. Everything up to a diagonal is a slip; a
# two-column jump with a different finger is somebody typing another word.
ADJACENT = 1.3


def plausible(word, candidate):
    """Whether one plausible slip explains the difference between the two.

    A dropped or doubled key explains any length difference, and a substitution
    explains itself only if the two keys are neighbours. This is what stops
    `cd` -- `a` mistyped as `d`, two keys away -- from being treated as just as
    likely as `cat`, which is `ca` with the last key missed.

    """
    return _misreach(_fold(word), _fold(candidate)) <= ADJACENT


def shape(word, candidate, edits):
    """Everything the metric knows about this candidate except its name.

    Two candidates with the same shape are the ones this module genuinely
    cannot tell apart, and a caller with another source of evidence -- your
    history, in `no_command` -- may choose between them. A caller that compares
    the distance alone is not comparing the metric: `cat` and `cd` are both one
    edit from `ca`, and the four terms after the distance are the whole reason
    `cat` is offered first.

    """
    anagram = sorted(word) != sorted(candidate)
    prefix = not (word.startswith(candidate) or candidate.startswith(word))
    return (edits, anagram, prefix, -_shared_opening(word, candidate),
            _misreach(word, candidate))


def _key_from(word, candidate, edits):
    """`_key`, for a caller that has already worked out the distance.

    Which both callers below have: `rank` computes it to decide whether to keep
    the candidate at all, and then `sort` recomputed it -- on every comparison,
    so O(n log n) times over a `PATH` of a few thousand names, for a value that
    had already been worked out once. `_fold` and `sorted()` went the same way.

    """
    return shape(word, candidate, edits) + (candidate,)


def _shared_opening(word, candidate):
    """How many characters the two agree on before they first differ."""
    shared = 0
    for first_char, second_char in zip(word, candidate):
        if first_char != second_char:
            break
        shared += 1

    return shared


def rank_with_distance(word, candidates, limit=None):
    """`rank`, with each candidate's edit distance beside it.

    For a caller that wants to know which candidates are equally good -- which
    `no_command` does, to break a tie on what the user has actually run. It
    used to ask `distance` again for every ranked name to find that out, having
    just been handed the answer.

    """
    folded = _fold(word)
    allowed = max_distance(folded)

    # `(key, candidate, edits)`: the distance and the fold are worked out once
    # per candidate here, rather than once per *comparison* inside `sort`.
    #
    # Deduplicated, as `order` below already was. A name can arrive twice --
    # `option_typo` reads `diff`'s options out of the printed usage *and* out of
    # `diff --help`, and `--color` is in both -- and then two of the three
    # suggestions offered were the same string. The corrector drops the
    # duplicate, so the cost was a wasted slot rather than a visible repeat.
    scored = []
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        folded_candidate = _fold(candidate)
        edits = distance(folded, folded_candidate, limit=allowed)
        if edits <= allowed:
            scored.append(
                (_key_from(folded, folded_candidate, edits), candidate, edits))

    scored.sort(key=lambda triple: triple[0])
    ordered = [(candidate, edits) for _, candidate, edits in scored]
    return ordered[:limit] if limit else ordered


def plausible_slips(word, ranked):
    """The candidates another source of evidence may reorder, best first.

    `ranked` is what `rank_with_distance` returned. A candidate qualifies when
    it is as close as the closest -- "never when it is worse" -- *and* when one
    plausible slip explains it, so that a caller with outside knowledge is
    choosing between real explanations rather than reordering the whole list.

    Comparing the distance alone is not enough, and that was the bug: `cat` and
    `cd` are both one edit from `ca`, so `cd` qualified as an equal and the
    history tie-break in `no_command` promoted it -- for everybody, since `cd`
    is the most-typed command there is.

    """
    if not ranked:
        return []

    best = ranked[0][1]
    return [candidate for candidate, edits in ranked
            if edits == best and plausible(word, candidate)]


def rank(word, candidates, limit=None):
    """The candidates worth offering for `word`, best first.

    Anything further away than `max_distance` is left out entirely: a wrong
    suggestion that looks confident is worse than no suggestion, and that is
    where `getent` for `wgte` and `pinky` for `ping` came from.

    """
    return [candidate
            for candidate, _ in rank_with_distance(word, candidates, limit)]


def order(word, candidates, limit=None):
    """`candidates` best first, keeping every one of them.

    The difference from `rank` is the filtering, and it matters. `rank` is for a
    list this tool built -- every executable on the machine -- where most
    entries are nothing to do with what was typed and offering them is how
    `pinky` came to answer `ping`.

    This is for a list the failing tool itself named: git's usage line, docker's
    command list, npm's scripts. Those are answers, not guesses, so none of them
    is thrown away -- they are only put in a sensible order.

    """
    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)

    folded = _fold(word)
    keyed = [(_key(folded, _fold(candidate)), candidate)
             for candidate in unique]
    keyed.sort(key=lambda pair: pair[0])
    ordered = [candidate for _, candidate in keyed]
    return ordered[:limit] if limit else ordered
