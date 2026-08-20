# The corpus

A list of typos a person really makes, and the suggestion they should get
first.

## Why it exists

There were 3,713 tests before this, and not one of them asked *"given this
typo, is the first suggestion sane?"* Every rule was tested on its own against
a hand-written fixture of its own tool's output. That shape cannot catch the
thing users actually hit, because the answer a user sees comes out of the
shared matching helpers and the ordering *across* rules -- and no rule owns
either. So the suite was green while `whomi` suggested `which`.

It is the *first* suggestion that matters, because that is the one enter runs.

## Why it is hermetic

Nothing here runs a shell, reads your `PATH`, or looks at your history.
`executables.txt` is a real `PATH` listing (580 names, captured from a Debian
container with the usual developer tools) and the history is a fixed list.

That is deliberate. The first version of this idea would have read the real
machine, and then the answer would depend on whose machine it ran on -- which
is exactly how `gti status` came to suggest `git status` here and `tic status`
in a container with no history. Same code, different answer, and no way to tell
a regression from a different laptop. It also has to give one answer on Windows.

## Regenerating

`executables.txt` is a snapshot and does not need refreshing often. The tool
outputs in `cases.py` were captured by running the real failing command; each
case says which tool and version it came from. Never write one by hand -- that
is how seven rules came to be green and dead at the same time.
