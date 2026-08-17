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
when exactly two subjects are given.

```
scenario                  fuck         bleep     ratio
------------------------------------------------------
alias                202.01 ms      82.55 ms     2.45x
correct-fast         237.22 ms     117.24 ms     2.02x
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
rule imports             21.2 ms       169
rule matching             1.1 ms        63
command re-run           14.0 ms         1
```

That table is the whole reason the optimisation work is ordered the way it is:
matching 169 rules is nearly free, loading them is not.

## The published numbers

`bench/results/final.json` is the run behind the table in the project README:
Python 3.11 on Linux, 30 runs per scenario, CPUs pinned. Re-running the harness
with `--json bench/results/final.json` replaces it, and `--baseline` compares
against it:

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
