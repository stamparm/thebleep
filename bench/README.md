# Latency harness

Every performance claim about The Bleep should be reproducible by someone who
does not trust it. That is what this directory is for.

## Quick start

```bash
./bench/setup_subjects.sh python3.11          # builds the subjects
./bench/bench.py \
    --subject fuck=bench/.venvs/fuck-3.11/bin/thefuck \
    --subject bleep=bench/.venvs/bleep-3.11/bin/thebleep
```

Output is a table of median wall-clock times per scenario, plus a ratio column
when exactly two subjects are given. The committed run in
`results/final.json` begins:

```
scenario                  fuck         bleep     ratio
------------------------------------------------------
alias                209.93 ms      27.77 ms     7.56x
version              208.65 ms      55.82 ms     3.74x
correct-fast         245.83 ms      55.87 ms     4.40x
```

## The scenarios

| Scenario | What it measures |
| --- | --- |
| `alias` | `--alias`, paid once per shell startup whether or not you ever use the tool |
| `version` | interpreter start plus the import graph, no rule work |
| `correct-fast` | a mistyped `git brnch`, the common case |
| `correct-nomatch` | nothing matches, so every rule gets consulted |
| `correct-slow` | the failed command takes 500 ms to re-run |
| `correct-in-repo` | inside a git repository, where the git rules do real work |
| `correct-big-output` | the failed command printed a megabyte first |
| `correct-wrapped` | `nice -n 10 git brnch`, corrected behind its wrapper — which upstream cannot do, so it has no baseline |

There is no `alias-loader` scenario, and deliberately: the loader runs no Python
at all, so what there would be to time is a shell defining a function, and the
difference between that and a shell doing nothing is smaller than the run-to-run
spread of starting a shell. Subtracting two noisy medians to four decimal places
is not a measurement.

`./bench/bench.py --list` prints them too.

## Tools

`hyperfine` is used when it is on `$PATH`, because its warmup handling and
statistics are better than a hand-rolled loop. Without it the harness falls
back to its own timing loop and reports the same fields, so numbers stay
comparable — the report header says which one ran.

```bash
cargo install hyperfine     # or your package manager
```

## Keeping the numbers honest

- **Pin the CPUs.** `BENCH_CPU=2,3 ./bench/bench.py ...` (or `--cpu 2,3`) runs
  every subject under `taskset` so a wandering scheduler does not decide the
  winner.
- **Measure both install shapes.** A wheel install has pre-compiled bytecode
  for the rules because pip compiles on install; a source checkout usually does
  not. `setup_subjects.sh` builds `bleep` and `bleep-src` for exactly this
  reason, and they are not interchangeable.
- **Say which Python.** Startup cost differs sharply across 3.9 → 3.14. The
  upstream baseline only exists up to 3.11, since `thefuck` imports `distutils`.
- **Compare against a stored run** rather than memory:

  ```bash
  ./bench/bench.py --subject bleep=... --json before.json
  # ... change something ...
  ./bench/bench.py --subject bleep=... --baseline before.json
  ```

- **Check the harness before trusting it.** Three runs on unchanged code should
  agree within a few percent. If they do not, the machine is too noisy to draw
  conclusions on.

## Where the time goes

`bench.py` says how long something takes; `profile_phases.py` says why, by
aggregating the app's own `--debug` timers and the `-X importtime` graph:

```bash
./bench/profile_phases.py --bin bench/.venvs/bleep-3.11/bin/thebleep --imports
```

```
phase                       time    events
------------------------------------------
rule imports              8.7 ms        86
rule matching             0.0 ms         2
unaccounted              23.3 ms
```

That table is the whole reason the optimisation work is ordered the way it is:
matching rules is nearly free, loading them is not — so the work went into
loading fewer of them, and `events` is how many were reached. The unaccounted
time is the interpreter starting and the failed command being read.

## The published numbers

`bench/results/final.json` is the run behind the table in the project README:
Python 3.11 on Linux, 30 runs per scenario, CPUs pinned. Its `environment` block
records the commit it was measured at, the kernel, the CPU and the harness's own
interpreter, so what it is a measurement *of* is not a matter of memory —
`git show <that commit>` is the source. Re-running the harness with `--json
bench/results/final.json` replaces it; `python bench/chart.py` then rewrites the
README's table from it, and `python bench/chart.py --check` fails if the two have
drifted apart. `--baseline` compares against it:

```bash
./bench/bench.py --subject bleep=... --baseline bench/results/final.json
```

## Reproducible environment

For numbers that can be compared across machines and across months, run inside
the pinned image:

```bash
docker build -t thebleep/bench -f bench/Dockerfile --build-arg PYTHON_VERSION=3.11 .
docker run --rm --cpuset-cpus=2,3 thebleep/bench
```


## The hit rate

`bench/hit_rate.py` answers a different question from the timings above: not how
fast, but how often the *first* suggestion is the right one. That is the one
<kbd>enter</kbd> runs, so it is the one worth counting.

```bash
python3 bench/hit_rate.py             # the table
python3 bench/hit_rate.py --compare   # ...beside The Fuck 3.32
python3 bench/hit_rate.py --record    # ...and write results/hit-rate.json
```

It measures [`tests/corpus/`](../tests/corpus/), which is real typos with the
output the real tool printed and a fixed `PATH`, so the answer does not move
between machines.

`--compare` needs `thefuck` importable. It does not start on Python 3.12, so the
comparison is run in a container with 3.11 and both tools installed:

```dockerfile
FROM python:3.11-slim
RUN python3 -m venv /opt/fuck311 \
    && /opt/fuck311/bin/pip install -q 'thefuck==3.32' psutil pyte
```

then, with the checkout mounted at `/clone`:

```bash
git config --global --add safe.directory /clone
cd /clone && TB_SHELL=bash TF_SHELL=bash \
    /opt/fuck311/bin/python bench/hit_rate.py --compare --record
```

Both tools are handed the identical `(script, output)` pair, the same `PATH` and
the same history, because anything else makes the comparison meaningless.

`--record` refuses a tree with uncommitted changes in it, and refuses when git
cannot say which commit it is: a measurement that cannot be traced to source is
not evidence. `tests/test_readme_claims.py` holds the README's table to the
recorded file.

**What the number is not.** It is our own corpus, chosen and generated by us. A
hundred percent on your own exam says the cases in it pass; it says nothing about
all typos everywhere. Its real job is to stop the tool getting worse -- the
corpus runs with every test run -- and to give anybody who finds a miss somewhere
concrete to put it.
