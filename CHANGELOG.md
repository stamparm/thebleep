# Changelog

## 4.0.0 — 2026-08-19

The first release of *The Bleep*, and the first release of this codebase since
*The Fuck* 3.32 in January 2022. The version continues *The Fuck*'s numbering
rather than restarting it, because this is the same codebase carried forward.

### It runs on current Python

- `distutils` is gone, which is what stopped *The Fuck* from starting on Python
  3.12 at all, and `pkg_resources` and `imp` went with it.
  ([#1499](https://github.com/nvbn/thefuck/issues/1499),
  [#1610](https://github.com/nvbn/thefuck/issues/1610),
  [#1552](https://github.com/nvbn/thefuck/issues/1552))
- Python 2 support removed.
  ([#1479](https://github.com/nvbn/thefuck/issues/1479),
  [#873](https://github.com/nvbn/thefuck/issues/873))
- Tested on Python 3.9 through 3.14, on Linux, macOS and Windows.

### Security

- The `sudo` rule no longer hands a re-quoted script to `sh -c` as root, where
  quoted data could be re-read as code.
- Filenames, branch names and URLs that rules read out of a failed command's
  own output are quoted before being put back into a command.
  (both [#1606](https://github.com/nvbn/thefuck/issues/1606))
- `open_command` quotes the URL it passes to the shell.
  ([#1531](https://github.com/nvbn/thefuck/issues/1531))

### Safety

- **The previous command is no longer run again without asking.** Correcting a
  command means knowing what it printed, and a shell keeps no record, so the
  command was run a second time — before any correction had been offered or
  agreed to. It is now confirmed first, unless there is no such program to run
  or the program is one that only ever reads. `confirm_replay = False` restores
  the old behaviour.
  ([#1126](https://github.com/nvbn/thefuck/issues/1126))

### Speed

Measured against *The Fuck* 3.32 on the same machine and the same Python 3.11,
median of 30 runs; the harness and the recorded run are in `bench/`.

- Opening a shell: 205 ms → 38 ms, or to 0.3 ms with `--alias-loader`, which
  defines the alias on first use so shell startup runs no Python at all.
- Correcting a mistyped command: 240 ms → 57 ms.
- Correcting after a command printed a megabyte: 3246 ms → 134 ms. This one is
  a correctness fix as much as a speed one: output used to be read only after
  the command exited, which deadlocks once the output fills the pipe buffer, so
  anything printing more than about 64 KB produced nothing to correct from.
- Rules are compiled once into a cache, and a command is only dispatched to the
  rules that could match it — around 30 of 170 rather than all of them.

### Rules

Refreshed against what the tools print today, found by running them rather than
by reading their old fixtures: `npm` 7+, `cargo` 1.73+, `docker` 25+, `brew` 4,
`gem` 3.2+, `az`, `gradle` 8, `terraform` 1.x, and `git` for `main` rather than
`master`. ([#1320](https://github.com/nvbn/thefuck/issues/1320),
[#1341](https://github.com/nvbn/thefuck/issues/1341),
[#1313](https://github.com/nvbn/thefuck/issues/1313))

- New rule `git_dubious_ownership`, for git refusing a repository it thinks
  somebody else owns.
  ([#1376](https://github.com/nvbn/thefuck/issues/1376))
- `brew install` no longer offers to install something when a `brew uninstall`
  failed, which it did because `install` is a substring of `uninstall`.
- Environment assignments are looked past when identifying a command, so
  `FOO=bar git brnch` is corrected.
  ([#1172](https://github.com/nvbn/thefuck/issues/1172))

### Fixed

- Crash walking an unreadable process tree, and on a process that exits while
  being killed. ([#1600](https://github.com/nvbn/thefuck/issues/1600),
  [#1509](https://github.com/nvbn/thefuck/issues/1509),
  [#1026](https://github.com/nvbn/thefuck/issues/1026),
  [#1040](https://github.com/nvbn/thefuck/issues/1040))
- Works with no terminal attached, and exits quietly on a closed pipe.
  ([#1562](https://github.com/nvbn/thefuck/issues/1562),
  [#1539](https://github.com/nvbn/thefuck/issues/1539))
- Works under `bash`/`zsh` with `set -u`, and with an empty alias value.
  ([#1355](https://github.com/nvbn/thefuck/issues/1355),
  [#1551](https://github.com/nvbn/thefuck/issues/1551))
- Fish history is read from the XDG data directory.
  ([#1258](https://github.com/nvbn/thefuck/issues/1258))
- Commands on Windows are found when the file is not spelled as typed.
  ([#1209](https://github.com/nvbn/thefuck/issues/1209),
  [#1296](https://github.com/nvbn/thefuck/issues/1296))
- The environment is no longer printed into debug output.
  ([#995](https://github.com/nvbn/thefuck/issues/995))
- The selection can be abandoned with the escape key.
  ([#1506](https://github.com/nvbn/thefuck/issues/1506))
- A correction is not applied when nobody confirmed it, which is what happened
  in a pipe, a subprocess or CI. Pass `--yes` to apply without asking.

### Renamed from The Fuck

The command is `thebleep`, the alias it installs is `bleep`, settings live in
`$XDG_CONFIG_HOME/thebleep/`, and environment variables are `THEBLEEP_*`. See
[Coming from The Fuck](README.md#coming-from-the-fuck) — the settings file
copies over unchanged, and `thebleep --alias-loader fuck` keeps the word you
are used to.
