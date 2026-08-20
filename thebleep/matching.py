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


def max_distance(word):
    """The furthest a candidate may be and still be worth offering.

    Roughly a quarter of the word, measured against the corpus rather than
    picked. The boundaries all earn their place: `gti` must not reach `tic` (two
    edits), `whomi` must not reach `which` (three), and `mkae` must not reach
    `man` -- two edits in a four-letter word is not a slip, it is a different
    word, and on a machine without `make` installed the honest answer is
    nothing at all.

    The cost is that a doubly-mangled short name cannot be reached either:
    `ndeo` is two edits from `node` and gets no suggestion. That is the trade,
    and it is the right way round -- a wrong answer offered confidently is worse
    than none, and single-slip typos are the overwhelming majority.

    """
    length = len(word)
    if length <= 4:
        return 1
    if length <= 8:
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
    edits = distance(word, candidate, limit=max_distance(word))
    anagram = sorted(word) != sorted(candidate)
    prefix = not (word.startswith(candidate) or candidate.startswith(word))
    return edits, anagram, prefix, -_shared_opening(word, candidate), candidate


def _shared_opening(word, candidate):
    """How many characters the two agree on before they first differ."""
    shared = 0
    for first_char, second_char in zip(word, candidate):
        if first_char != second_char:
            break
        shared += 1

    return shared


def rank(word, candidates, limit=None):
    """The candidates worth offering for `word`, best first.

    Anything further away than `max_distance` is left out entirely: a wrong
    suggestion that looks confident is worse than no suggestion, and that is
    where `getent` for `wgte` and `pinky` for `ping` came from.

    """
    allowed = max_distance(word)
    scored = []

    for candidate in candidates:
        if not candidate:
            continue
        edits = distance(word, candidate, limit=allowed)
        if edits <= allowed:
            scored.append(candidate)

    scored.sort(key=lambda candidate: _key(word, candidate))
    return scored[:limit] if limit else scored


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

    unique.sort(key=lambda candidate: _key(word, candidate))
    return unique[:limit] if limit else unique
