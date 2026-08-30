# The Bleep [![Version][version-badge]][version-link] [![Build Status][workflow-badge]][workflow-link] [![MIT License][license-badge]](LICENSE.md)

**The maintained successor to [The Fuck](https://github.com/nvbn/thefuck).**

Type the command wrong. Type `bleep`. Run the right one.

![The Bleep correcting a mistyped command](assets/demo.svg)

## Get it

```bash
curl -fsSL https://raw.githubusercontent.com/stamparm/thebleep/master/install.sh | sh
```

That picks up whichever of `uv`, `pipx` or `pip` you already have, and prints
the one line to add to your shell's startup file. Prefer to do it yourself:

```bash
uv tool install thebleep          # or: pipx install thebleep
thebleep --alias-loader >> ~/.bashrc
```

Open a new shell, and the next time you mistype something, type `bleep`.
[The long version](#installation), including the muscle memory you already
have:

```bash
thebleep --alias-loader fuck >> ~/.bashrc
```

## Why not just The Fuck

Because the idea deserves better than its last release. *The Fuck* 3.32 is from
January 2022: it cannot start on Python 3.12 or newer, over three hundred
issues are open on it, and a good number of its rules quietly stopped matching
when the tools they correct changed what they print. *The Bleep* is the same
tool, maintained — and several times quicker about it.

Same machine, same Python 3.11, 30 runs each, medians:

<!-- benchmark: written by bench/chart.py -->
```text
                               % of The Fuck's time  The Fuck  The Bleep  faster
Open a shell                     ██▌░░░░░░░░░░░░░░░    206 ms      29 ms    7.1×
Correct a mistyped command       ████▌░░░░░░░░░░░░░    240 ms      60 ms    4.0×
Correct inside a git repository  ████░░░░░░░░░░░░░░    248 ms      54 ms    4.6×
Correct when nothing matches     ███▉░░░░░░░░░░░░░░    333 ms      72 ms    4.6×
Correct a slow command *         ████████████▍░░░░░    816 ms     562 ms    1.5×
Correct after 1 MB of output     ▋░░░░░░░░░░░░░░░░░    3.25 s     114 ms   28.4×
```
<!-- end benchmark -->

\* that command sleeps for half a second. Both tools have to sit through it to
read what it printed, so this row is mostly the sleep.

Opening a shell is worth a second look: that row is `eval "$(thebleep --alias)"`
in your rc, which starts a Python interpreter every time. Use the
[loader](#the-alias-and-why-it-costs-nothing) instead and opening a shell defines
a shell function and **runs no Python at all** — the 29 ms goes, and what is left
is too small to measure honestly against the noise in shell startup.

Those are Linux numbers, on the machine named in the result file. Windows and
PowerShell are exercised in CI on every push; [On Windows](#on-windows) is about
what makes a correction expensive there and what was done about it.

The harness is [`bench/`](bench/README.md), the run these numbers come from is
[`bench/results/final.json`](bench/results/final.json), and the block above is
written from that file by [`bench/chart.py`](bench/chart.py). [Reproduce it, and
read where the time went](#performance).

It is also right more often, which in the end matters more than being quick.
The same 85 typos — real commands, with the output the real tool printed — put
to both:

<!-- hit-rate: written by bench/hit_rate.py --compare -->
| what went wrong | for example | The Bleep | The Fuck 3.32 |
| --- | --- | --- | --- |
| you misspelled the command itself | `gti status` | **56/56** | 46/56 |
| the tool named the fix itself | `git satus` | **20/20** | 6/20 |
| nothing should be suggested | `zzzzzqqqq` | **9/9** | 3/9 |
| **all 85 of them** |  | **85/85 (100%)** | 55/85 (65%) |
<!-- end hit-rate -->

Only the *first* suggestion counts, because that is the one <kbd>enter</kbd>
runs. What each row is asking:

**You misspelled the command itself.** The shell could not find the program, so
`command not found` is the entire evidence and the fix has to be guessed from
what is installed — `gti status` is `git status`, `whomi` is `whoami`. This is
the biggest group because it is the commonest mistake, and it is the one where
guessing badly is easiest: on a machine with several thousand executables,
something is always *nearly* spelled like your typo.

**The tool named the fix itself.** The program ran, and its own error message
contains the answer: git prints `the most similar command is status`, npm lists
the scripts in your `package.json`, `ls --sort=nmae` prints every value `--sort`
accepts. Nothing has to be guessed here — it only has to be *read*. Getting one
of these wrong means ignoring an answer already on the screen, which is why 6 of
20 is the number to look at: those rules were written against wordings the tools
have since changed, and nobody noticed because a rule that stops matching just
goes quiet.

**Nothing should be suggested.** Commands where every possible correction is
wrong, so the right behaviour is to say nothing: `zzzzzqqqq` is not a typo of
anything, `ls -la` worked fine, `mv typoo.txt new.txt` is missing its *source*
so there is no directory to go and create. What this row measures is whether the
tool knows when to shut up — and it is the row worth reading twice, because The
Fuck offers something anyway two times in three. A wrong suggestion sitting one
keystroke from running is worse than no suggestion at all, which is the whole
reason this group is in the corpus and scored.

Read that 100% with the scepticism it deserves — it is our own corpus, chosen
and generated by us, and a number on your own exam is not a number about the
world. What it is good for is stopping the tool getting worse:
[`tests/corpus/`](tests/corpus/) runs with every test run, so a regression in
suggestion quality fails the build. Reproduce it with
`python3 bench/hit_rate.py`, or add a case that it gets wrong and send it.

It reproduces because the benchmark stubs out everything that would otherwise
make the answer a fact about your machine — `PATH`, the shell history, and
Debian's `command-not-found` database, which would have `sl` answered with
`apt-get install sl` on a machine that has it and `ls` on one that does not.
Both tools are given the identical question.

The rest of the reasons:

- **Python 3.9 through 3.14**, tested on Linux, macOS and Windows on every one
  of them — and Bash, Zsh, Fish, tcsh and PowerShell as before, with
  Nushell added. [Supported everything](#supported-everything).
- **30 items from *The Fuck*'s backlog are fixed here**, issues and pull
  requests, four of them command injections — plus the rules that had rotted
  against current
  `git`, `npm`, `docker`, `cargo`, `brew`, `gem`, `az`, `gradle` and
  `terraform`. [What's fixed](#whats-fixed).
- **It asks before running your previous command a second time.** Reading what
  your command printed used to mean running it again, side effects and all.
  [Safe by default](#safe-by-default).
- **Press tab to edit the correction instead of running it.** The suggestion
  lands in your own command line, with the cursor at the end of it, and nothing
  runs until you press return. [Edit before you run](#edit-before-you-run).
- **Press `?` to be told why.** Which rule made the suggestion, what it saw,
  and whether accepting it does anything besides run the command.
  [Why am I being told this](#why-am-i-being-told-this).
- **It remembers the last five failed commands.** `thebleep --pick` lists them;
  `thebleep --pick 2` corrects one using its captured output and working
  directory, without replaying it. `thebleep --forget 2` removes one record;
  `--clear-cache` removes them all. The records are local and bounded.
- **It can learn an explicit correction.** After accepting a one-word fix,
  `thebleep --learn-last` saves it locally for the executable; `global` and
  `repository` scopes are available when the same correction should travel
  further. `thebleep --learned` lists the entries and
  `thebleep --forget-learning 2` removes one.
- **A structured Python API.** IDEs and agents can supply a command and its
  captured output without asking The Bleep to run anything again.
  [Structured API](#structured-api).
- **It can explain failures that are not typos.** `--why` recognises a small,
  deterministic set of error fingerprints and suggests read-only next steps;
  unknown failures remain an abstention.
  [Structured API](#structured-api).
- **`thebleep --doctor`** answers the questions a bug report usually starts
  with, in one screen you can paste anywhere.
  [Diagnostics](#thebleep---doctor).
- **Nothing to relearn.** The same rules and settings, and the same `fuck` alias
  if you want it; seven rules are deliberately less eager, all in the direction
  of doing only what they say. [Coming from The Fuck](#coming-from-the-fuck).

*The Bleep* is based on the original codebase by Vladimir Iakovlev and its
contributors; their work and history remain fully credited.

## Contents

1. [Safe by default](#safe-by-default)
2. [Edit before you run](#edit-before-you-run)
3. [Why am I being told this](#why-am-i-being-told-this)
4. [Recent failures](#recent-failures)
5. [Learned corrections](#learned-corrections)
6. [Structured API](#structured-api)
7. [thebleep --doctor](#thebleep---doctor)
8. [Coming from The Fuck](#coming-from-the-fuck)
9. [What's fixed](#whats-fixed)
10. [Supported everything](#supported-everything)
11. [Installation](#installation)
12. [Updating](#updating)
13. [Uninstall](#uninstall)
14. [How it works](#how-it-works)
15. [Creating your own rules](#creating-your-own-rules)
16. [Settings](#settings)
17. [Third-party packages with rules](#third-party-packages-with-rules)
18. [Experimental instant mode](#experimental-instant-mode)
19. [Performance](#performance)
20. [Developing](#developing)
21. [License](#license-mit)

## Safe by default

*The Bleep* asks before running a correction. In a non-interactive environment
(pipe, subprocess or CI), it does **not** silently apply the first suggestion;
use `--yes` when you explicitly want automatic application.

### Reading the previous command

To suggest a fix, *The Bleep* needs to know what your command printed — and a
shell keeps no record of that. The only way to find out is to run the command
again, which means anything it changed changes twice:

```bash
$ deploy production
deploy: missing --confirm
$ bleep
deploy production has to run again to be read, and anything it changes will
change twice. Run it? [y/N]
```

So it asks first. It skips asking in three cases.

**There is no such program**, so nothing runs either time — `gti status`.

**You mistyped a subcommand.** `git satus` is not a `git push`: git does nothing
whatever until it has recognised a subcommand, so one it does not have fails at
dispatch the second time exactly as it did the first. The subcommands are not
written down anywhere here — git is asked for its own list, so one added after
this was written is not mistaken for a typo. A subcommand git *does* have is
still a question, `git status` along with `git push`, because whether it writes
depends on the flags. So is an alias, which git lists as its own: `st` can stand
for anything, `!deploy.sh` included. And so is anything with git's own options
in front of the subcommand (`git -C /tmp satus`) — working out which of them
take a value, and which of the remaining words is therefore the subcommand
rather than a path, is the kind of nearly-right that would run `git -C /tmp
push` again unasked.

`cargo` works the same way, from `cargo --list`. `npm`, `docker`, `uv`,
`apt-get`, `kubectl` and `yarn` do not, and the reason is worth knowing: the
list a program gives has to contain *every* word it will dispatch on, or a
missing one looks like a typo and its command runs again unasked.

- `npm uninstal` appears in neither `npm help` nor `npm -l`, runs, and takes the
  dependency out of your `package.json` — npm accepts any unambiguous
  abbreviation, so it dispatches on far more words than it prints.
- `uv build-backend` is in neither `uv --help` nor `uv help`, and runs.
- `docker` is the sharpest case, because its list looks complete: a CLI plugin
  is printed as `compose*`, with the asterisk. The word that dispatches is
  `compose`, which is therefore *not* in the list — so `docker compose up -d`
  would be taken for a typo and your stack brought up twice.
- `apt-get`'s help calls itself "Most used commands" and points at the manual
  page, which is the program declining to claim completeness. `full-upgrade` is
  missing from it.
- `yarn` can never qualify: an unrecognised word is looked up as a script in the
  local `package.json`, so its dispatch set is whatever directory you are in.

A `--help` screen is a document laid out for a person, not a promise about what
the program accepts.

**The program only ever reads**, whatever it is asked to do — `ls`, `cat`,
`grep`. That last one is a judgement about the *name*, and a name is not a proof
about the program a `PATH` lookup will find; what makes it a reasonable one is
that the same program under the same name ran a moment ago, when you typed it.
It is deliberately *not* a list of dangerous commands: such a list only declares
the ones nobody thought of to be safe. It is also why no subcommand dispatcher
is on it — `git branch` reads and `git branch -d` deletes.

Where nobody can be asked — a pipe, a subprocess, CI — the answer is no, and
the correction is attempted from the command alone.

Two ways to stop being asked:

- **Record the output as it happens.** [Experimental instant
  mode](#experimental-instant-mode) reads what scrolled past instead of running
  anything again, so the question never comes up. This is the better answer if
  your shell supports it.
- **`confirm_replay = False`** in your settings, or `--yes` for a single run,
  which restores *The Fuck*'s behaviour of running the previous command again
  without asking.

## Edit before you run

A suggestion is often ninety-five percent of what you wanted. Press <kbd>tab</kbd>
instead of <kbd>enter</kbd> and it is handed to you in your own command line to
finish:

```bash
$ git chekout featuer
git: 'chekout' is not a git command. See 'git --help'.
$ bleep
git checkout feature [enter/↑/↓/tab=edit/?/ctrl+c/esc]
```

<kbd>tab</kbd>, and the next thing you see is your own prompt, with the cursor
after the last character:

```bash
$ git checkout feature█
```

From there it is an ordinary command line: edit it, or press return to run it,
or <kbd>ctrl+c</kbd> to throw it away. Nothing has run yet. `bleep --edit` (or
`-e`) makes that the behaviour of <kbd>enter</kbd> too, and `edit = True` in
your settings makes it permanent — a mode where *The Bleep* never runs anything,
it only writes your next command for you.

The arrow keys still walk the other suggestions, so you can pick the one worth
editing before you edit it.

### Inline correction before execution

For a command that has not run yet, print an opt-in <kbd>Esc Esc</kbd> binding
for your shell and add it to your shell configuration:

```bash
thebleep --bind-inline >> ~/.bashrc
```

Then type a command such as `gti status`, press <kbd>Esc Esc</kbd>, and the
correction is placed in the current line for you to inspect. It is not run
until you press return. Bash 4+, Zsh and Fish are supported; the other shells
leave the binding unavailable rather than injecting keystrokes into the
terminal.

Inline correction has no command output to inspect, so rules that require
stderr are skipped. The generic command lookup can still use your PATH and
shell builtins, including a misspelled command inside `$(...)`. Use
`--inline --command 'gti status'` to try the same non-executing lookup without
a line editor.

### Which shells

The correction goes into the line editor through whatever the shell offers for
exactly that. There is no fallback for the shells that offer nothing: the trick
that would work everywhere is `TIOCSTI`, which pushes characters into another
process's terminal as though they had been typed. Modern Linux can refuse it
outright, and does by default — for good reasons that apply here too.

| Shell | How | What you get |
| --- | --- | --- |
| Zsh | `print -z` | your next prompt, already filled in |
| Fish | `commandline --replace` | your next prompt, already filled in |
| Nushell ≥ 0.87 | `commandline edit --replace` | every correction, always |
| Bash ≥ 4.0 | `read -e -i` | a readline prompt, already filled in |
| PowerShell | `PSConsoleReadLine::AddToHistory` | press <kbd>↑</kbd> to bring it up |
| Bash 3.2 (macOS system bash) | — | not offered |
| tcsh | — | not offered |

Bash is the one that is close rather than exact. It has no way to write the
*next* prompt's buffer, so what you get is readline itself — your keymap, your
history, your editing keys — on a line that already holds the correction, and
the prompt is your own `PS1`. PowerShell's editing API belongs to a key handler
and does nothing when called from a function, so there the correction becomes
the newest history entry and one <kbd>↑</kbd> brings it up.

Where editing is not available, <kbd>tab</kbd> is not offered and does nothing;
`--edit` says so and runs nothing rather than falling back to running the
command. The prompt tells you which case you are in: if it says `tab=edit`, it
works.

Editing does not fire a rule's side effect and does not touch your history. Both
belong to a command that ran, and an edited one has not — your shell records
whatever you finally submit, which is the command you actually chose.

### Nushell

Nushell is the shell where this is not an option but the whole design, so it is
worth saying plainly what happens: **a correction always goes to your command
line, and you press return to run it.**

```
> gti status
Error: nu::shell::external_command
  × External command failed
> bleep
git status [enter/↑/↓/ctrl+c/esc]
> git status█
```

That is not a shortcoming worked around. Nushell has no `eval`, deliberately —
it parses a script all the way through before running any of it, which is where
most of what it can tell you about a pipeline comes from, and code that appears
at run time cannot be parsed that way. `nu -c '...'` is not a substitute: it
starts a second Nushell, so a corrected `cd`, `mkdir -p x; cd x` or `$env`
assignment would happen to a process that immediately exits, and a correction
that silently does nothing is worse than no correction. Writing it into your
command line runs it in the session you are actually in.

Two smaller differences follow from the same place. `and`/`or` in Nushell are
boolean operators and not command separators, so a chained correction is written
`try { git pull; git push }` — `try` stops at the command that failed, which is
what `&&` means. And the broken command is not removed from your history, since
Nushell has no way to delete an entry; the corrected one is recorded normally
when you submit it.

Nushell 0.87 or newer, which is where `commandline edit` arrived.

## Why am I being told this

A correction is a command you are about to run, and "because a program said so"
is a thin reason to run anything. Press <kbd>?</kbd> at the prompt:

```bash
$ git chekout featuer
$ bleep
git checkout feature [enter/↑/↓/tab=edit/?/ctrl+c/esc]
  rule     git_not_command (bundled)
  matched  git, and output containing "is not a git command. See 'git --help'."
  read     what your command printed
git checkout feature [enter/↑/↓/tab=edit/?/ctrl+c/esc]
```

Two more lines appear when they apply: `side effect`, when accepting the
suggestion does something besides run the command, and `runs as`, when the
correction begins with `sudo` or `doas`. Having asked once, the arrow keys
explain each suggestion as you walk them. `bleep --explain` starts that way, and
`explain = True` in your settings makes it permanent.

Everything there is a fact about the rule rather than a description of it: its
name, which of the three places its file came from, whether it declares that it
needs your command's output, whether it has a side effect — and then the two
that carry most of the meaning, the app it says it is about and the text it
requires in the output, both read out of the rule's own `match` by the same
extraction that decides which rules to load at all. Where several messages would
have satisfied the rule, the one quoted is the one that is actually in your
output.

Nothing reads a rule's body and tries to say in English what it means, and no
rule had to be given a hand-written description for this to work — so a rule of
your own, or one from a package, explains itself exactly as well as a bundled
one does. A rule that works its condition out in a way this cannot read says so:
`matched  a condition this rule works out for itself`.

##### [Back to Contents](#contents)

## Recent failures

The alias records the last five non-zero failures with their command, captured
output, shell, exit status and working directory. The record is capped at 1 MiB
per failure and is only a local cache; command lines and output can contain
sensitive data, so `thebleep --clear-cache` removes it with the other caches.

```bash
thebleep --pick       # list the failures
thebleep --pick 2     # correct the second one, without replaying it
thebleep --forget 2   # remove the second one
```

If its original directory no longer exists, correction continues from the
current directory and says so. A stored failure is never executed merely by
listing or selecting it; the normal confirmation and edit-before-run rules
still apply.

##### [Back to Contents](#contents)

## Learned corrections

Learning is explicit and deliberately narrow. When you accept a normal
correction, *The Bleep* keeps one temporary candidate. Run
`thebleep --learn-last` to promote it; only a simple command with exactly one
changed shell word is eligible. Side-effect suggestions and edits are not
learned, because an edit can contain anything the shell line editor accepted.

```bash
thebleep --learn-last              # keep it for this executable
thebleep --learn-last global       # keep it wherever the command appears
thebleep --learn-last repository   # keep it below the current Git root
thebleep --learned                 # inspect the local list
thebleep --forget-learning 2       # remove entry 2
```

Entries are stored locally in the normal *The Bleep* configuration directory,
limited to 100, and never uploaded. Matching is exact for every other word in
the command, so a learned `corpctl deply payments` correction cannot rewrite a
different command or an unrelated argument. Repository entries also require a
Git root and do not match outside it.

##### [Back to Contents](#contents)

## Structured API

For an editor, IDE or agent that already has the failed command's output, use
the deterministic engine without invoking a shell:

```python
from thebleep.api import suggest

result = suggest('git chekout feature', "git: 'chekout' is not a git command")
for item in result['suggestions']:
    print(item['command'], item['rule'], item['evidence'])
```

The result includes `schema: 1` for contract versioning, the original command,
whether output was supplied, and a `decision`: `suggest` when a candidate passed
the rules, or `abstain` when no candidate was verified. Each suggestion contains
its command, rule, priority,
side-effect flag, conservative risk markers and evidence. `risk: low` means
that no known high-risk marker was found; it is not a safety guarantee. The
`explanation` field keeps the same facts with labels, so a consumer can tell
matched output from the read requirement, side effect or privilege change
without parsing prose. If output is omitted, output-dependent rules are
skipped; the API never replays a command to fill it in.

The same contract is available from the command line:

```bash
thebleep --json --stderr error.txt --cwd "$PWD" --command 'gti status'
```

`--stderr -` reads captured output from standard input. Input is bounded at
8 MiB; an unexpectedly large capture is rejected rather than buffered without
limit. The Python API applies the same 8 MiB output limit. `--command` preserves
the exact command string, including compound
syntax and quoting; the older positional form after `--` remains supported.

When the command itself is valid but failed, ask for a deterministic diagnosis
from the same captured output:

```python
from thebleep.api import why

result = why('python client.py --port 5432',
             'OSError: [Errno 98] Address already in use')
```

The result uses the same versioned envelope and returns `diagnoses` with the
observed evidence, a short summary and read-only `next_steps`. It covers a
small set of high-signal failures such as occupied ports, DNS resolution
failures, missing Python paths/modules and Git's repository/ownership refusals. It never
probes the machine or reruns the command. Unknown wording returns
`decision: abstain`, because a plausible explanation is not proof. Follow-up
commands are selected for the
current platform; callers using the Python API can pass `platform_name='nt'`
when diagnosing output for a Windows target from another machine.

The command-line form is:

```bash
thebleep --json --why --stderr error.txt --command 'python app.py'
```

Use `--platform nt` when diagnosing Windows output from another platform;
`posix` is the default for POSIX output.

##### [Back to Contents](#contents)

## thebleep --doctor

When something is not working, it is nearly always one of a dozen things, and
every one of them is a fact about the machine rather than about the code — the
alias is in a file this shell does not read, `thebleep` on `PATH` is an older
copy in another virtualenv, the settings file has a typo so every setting in it
was dropped, `~/.config/thefuck` was never copied over. `--doctor` checks all of
them at once:

```
$ thebleep --doctor
  The Bleep           4.0.0
  Python              3.12.3 (/usr/bin/python3)
  Platform            Linux 6.8.0 (x86_64)
  Shell               ZSH 5.9 (from TB_SHELL)
  Integration         alias loader in ~/.zshrc
  Executable          ~/.local/bin/thebleep
  On PATH             yes
  Config              ~/.config/thebleep/settings.py (2 set: priority, rules)
  Rules               186 bundled, 3 of your own
  Rule health         169 enabled, none raising
  Rule pack           ~/.cache/thebleep/rules-3-cb0d0d0a.pack (186 rules cached)
- Replayless capture  available, not switched on
                      See --enable-experimental-instant-mode.
  Editing             supported by this shell (tab at the prompt)

Everything looks good.
```

`!` marks something worth fixing and the advice sits under it; `-` is worth
knowing. The exit status is non-zero when there is a `!`, so it is usable in a
script.

**It is safe to paste.** A diagnostic ends up in an issue, so it says that a
setting is set and not what it is set to, that an alias is defined and not what
it expands to, which rules exist and not what is in them. Nothing is read out of
the environment except the handful of names *The Bleep* itself defines, and
those are reported as set or unset. Paths have your home directory folded back
to `~`, so your username does not travel either.

**It changes nothing.** No config directory is created, no settings file is
written, no rule pack is built — a report that has to alter the machine before
it can describe it is describing a different machine.

##### [Back to Contents](#contents)

## Coming from The Fuck

Nothing is relearned. The rules, the settings and the flags are the ones you
already know; the names changed and the config moved.

```bash
pip uninstall thefuck                       # optional, they coexist happily
cp -r ~/.config/thefuck ~/.config/thebleep  # settings.py and your own rules
```

Then swap the line in your startup file. Keeping the word you are used to is
one argument:

```bash
thebleep --alias-loader fuck >> ~/.bashrc   # and delete the thefuck line
```

What to know:

- `THEFUCK_*` environment variables are `THEBLEEP_*`. The names after the
  prefix are unchanged.
- Config is `$XDG_CONFIG_HOME/thebleep/settings.py`, and your own rules go in
  `$XDG_CONFIG_HOME/thebleep/rules`. The settings themselves are the same, so
  the file copies straight over.
- A rule of your own that imports `thefuck.utils` wants `thebleep.utils`. That
  is the whole of the port.
- A rule *package* of your own is `thebleep_contrib_*` rather than
  `thefuck_contrib_*`.
- *The Bleep* asks before running your previous command a second time.
  `confirm_replay = False` in your settings restores what you are used to, and
  [Reading the previous command](#reading-the-previous-command) explains why
  you might not want to.

Seven rules behave differently on purpose, all in the same direction — what you
agree to is what runs:

- `dirty_untar` and `dirty_unzip` suggest extracting into a directory of their
  own, and no longer delete the files that were already unpacked. They could not
  tell an extracted file from one of yours under the same name, and their
  containment check was a string prefix that `../` walks straight out of.
- `ssh_known_hosts` shows you the `ssh-keygen -R` it wants to run, in front of
  your command. It used to hand back your own command and remove the offending
  line behind it, so a man-in-the-middle warning disappeared with nothing to
  read.
- `rm_dir` adds `-r`, not `-rf`. `-r` is enough to remove a directory; `-f` also
  silences the prompt for a write-protected file.
- `pip_install` no longer falls back to `sudo pip install`.
- `python_module_error` is off by default. An import name is not a distribution
  name — `import yaml` wants PyYAML — so the package it suggests installing is a
  guess, and a mistyped import makes it `pip install <typo>`. Ask for it with
  `rules = ['DEFAULT_RULES', 'python_module_error']`.
- `quotation_marks` only fires when your command genuinely does not parse and
  swapping the quotes makes it parse. It used to fire whenever both kinds of
  quote appeared and rewrite them, so `git commit -m "it's fine"` became
  `git commit -m "it"s fine"`.

##### [Back to Contents](#contents)

## What's fixed

Every commit that fixes a reported problem names the issue it fixes, so this is
`git log --grep 'nvbn/thefuck#'` rather than a claim in a README. Thirty
upstream backlog items so far — half of them issues and half of them pull
requests nobody merged — every one of them linked below, and the rest found by
running the tools.

**It starts on current Python.** `distutils` was removed in 3.12 and *The Fuck*
imports it, so it cannot run there at all; `pkg_resources` and `imp` were going
the same way. All three are gone, Python 2 support went with them, and the
suite runs on 3.9 through 3.14 on Linux, macOS and Windows.
&nbsp;<sub>[#1499](https://github.com/nvbn/thefuck/pull/1499)
[#1610](https://github.com/nvbn/thefuck/pull/1610)
[#1552](https://github.com/nvbn/thefuck/issues/1552)
[#1479](https://github.com/nvbn/thefuck/pull/1479)
[#873](https://github.com/nvbn/thefuck/pull/873)</sub>

**Four ways a command could be turned into a different command.** A correction
is text a shell then evaluates, and much of that text is copied out of somewhere
you do not control — a tool's error message, a repository's branches, a package
file's scripts — where shell syntax is perfectly legal: git will make you a
branch called `feature;rm -rf ~`. Unquoted were the names the `*_no_command`
rules read out of another command's output; the paths and names read out of the
failed command's own output, `ssh`'s `known_hosts` line and a branch from
`origin/HEAD` among them; the URL handed to `open`; and the `sudo` rule, which
re-quoted your whole script and gave it to `sh -c` as root. All four are quoted
now, and [`tests/test_injection.py`](tests/test_injection.py) runs each
suggestion through a real shell and checks what the program actually received.
&nbsp;<sub>[#1531](https://github.com/nvbn/thefuck/issues/1531)
[#1606](https://github.com/nvbn/thefuck/issues/1606)</sub>

**It asks before running your command again.** To correct a command you have to
know what it printed, and a shell keeps no record, so the command is run a
second time — `deploy`, `git push`, `rm`, whatever it was, before you have
agreed to anything. It asks first now, except where there is nothing to run or
the program only ever reads.
&nbsp;<sub>[#1126](https://github.com/nvbn/thefuck/issues/1126)</sub>

**The alias breaking because of something you pasted.** The shell handed us your
recent history in an environment variable, and the kernel will not pass a program
a variable larger than 128K. One pasted command that size and the alias failed
with "Argument list too long" — for that correction and for every one afterwards,
until the entry fell out of the history window. It asks the shell for a smaller
window instead.
&nbsp;<sub>[#798](https://github.com/nvbn/thefuck/issues/798)</sub>

**Rules that had quietly stopped matching.** A rule that looks for a string in
a tool's output stops working the day that tool rewords it, silently, and
nothing in a test suite of fixtures notices. These were found by mistyping
commands at the installed binaries and reading what came back: `npm` 7+,
`cargo` 1.73+, `docker` 25+, `git` (`main` rather than `master`, and repository
ownership), `brew` 4 (five of its seven rules), `gem` 3.2+, `az`, `gradle` 8 and
`terraform` 1.x.
&nbsp;<sub>[#1320](https://github.com/nvbn/thefuck/issues/1320)
[#1172](https://github.com/nvbn/thefuck/issues/1172)
[#1341](https://github.com/nvbn/thefuck/issues/1341)
[#1313](https://github.com/nvbn/thefuck/issues/1313)
[#1376](https://github.com/nvbn/thefuck/issues/1376)</sub>

**Crashes, and the places it did not work at all.** An unreadable process tree,
a process that exits while being killed, no terminal attached, a closed pipe,
`set -u`, an empty alias, Fish's history moving to the XDG data directory, a
command on Windows whose file is not spelled the way you typed it, and your
environment being printed into debug output.
&nbsp;<sub>[#1600](https://github.com/nvbn/thefuck/pull/1600)
[#1509](https://github.com/nvbn/thefuck/issues/1509)
[#1026](https://github.com/nvbn/thefuck/issues/1026)
[#1040](https://github.com/nvbn/thefuck/issues/1040)
[#1562](https://github.com/nvbn/thefuck/pull/1562)
[#1539](https://github.com/nvbn/thefuck/pull/1539)
[#1355](https://github.com/nvbn/thefuck/pull/1355)
[#1551](https://github.com/nvbn/thefuck/pull/1551)
[#1258](https://github.com/nvbn/thefuck/pull/1258)
[#1209](https://github.com/nvbn/thefuck/issues/1209)
[#1296](https://github.com/nvbn/thefuck/issues/1296)
[#995](https://github.com/nvbn/thefuck/pull/995)
[#1506](https://github.com/nvbn/thefuck/pull/1506)</sub>

**And the test suite itself.** Three of the thirty are about the tests rather
than the tool: `mock` became `unittest.mock`, a memoized helper leaked
between test cases, and `usefixtures` was applied to a fixture, where it does
nothing.
&nbsp;<sub>[#1344](https://github.com/nvbn/thefuck/pull/1344)
[#1523](https://github.com/nvbn/thefuck/pull/1523)
[#1550](https://github.com/nvbn/thefuck/pull/1550)</sub>

**And it is quicker**, which has [a section of its own](#performance).

##### [Back to Contents](#contents)

## Supported everything

| | |
| --- | --- |
| **Python** | 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 |
| **Systems** | Linux, macOS, Windows — every Python on every one of them, on every push |
| **Shells** | Bash, Zsh, Fish, Nushell, tcsh, PowerShell |
| **Rules** | 186 of them, for git, docker, npm, yarn, pip, apt, dnf, zypper, pacman, brew, cargo, go, gradle, maven, terraform, aws, az, systemctl and the rest |

Bash, Zsh, Fish, Nushell and tcsh are exercised end to end, in containers,
driving a real terminal: the tests type a wrong command into the shell, type the
alias, and check what the shell then runs. PowerShell gets the same treatment on
Windows in CI, in Windows PowerShell 5.1 as well as 7, because the two do not
agree about command chaining. The Python suite covers all six.

##### [Back to Contents](#contents)

## Installation

The one-liner picks up whichever of `uv`, `pipx` or `pip` you already have,
never asks for `sudo`, and never edits a file of yours:

```bash
curl -fsSL https://raw.githubusercontent.com/stamparm/thebleep/master/install.sh | sh
```

Read it first if you like — that is the same file as
[`install.sh`](install.sh) in this repository, and `sh install.sh --dry-run`
prints what it would run without running it.

Or do it by hand, in whichever way you install command line tools:

```bash
uv tool install thebleep      # https://docs.astral.sh/uv/
pipx install thebleep         # https://pipx.pypa.io/
pip install --user thebleep   # if your distribution lets pip write there
```

The first two put *The Bleep* in an environment of its own, which is what you
want for a tool rather than a library: nothing you `pip install` later can break
it. On Debian, Ubuntu and Fedora, `pip install --user` is refused outright
([PEP 668](https://peps.python.org/pep-0668/)) — use `uv` or `pipx` there.

### Running a clone, with nothing installed

There is nothing to build and no install step — but there are two dependencies,
and the interpreter you point at has to have them:

```bash
python3 -m pip install --user psutil pyte
```

Then one line in your startup file, and the clone *is* your *The Bleep* — a
`git pull` is the whole upgrade. It is one line per shell, because the way a
shell reads code from a command is the one thing they never agree on:

```bash
# bash, zsh — and fish, which has understood $(…) since 3.4
eval "$(python3 ~/src/thebleep/thebleep/__main__.py --alias-loader)"
```

```fish
# fish, the native form
python3 ~/src/thebleep/thebleep/__main__.py --alias-loader | source
```

Nushell has no `eval` (see [Nushell](#nushell) for why), and `source` is
resolved when a script is parsed rather than as it runs — so it cannot be one
line. Write the loader out once, and `source` the file from your `config.nu`:

```nu
python3 ~/src/thebleep/thebleep/__main__.py --alias-loader | save -f ~/.thebleep.nu
# then, in config.nu:  source ~/.thebleep.nu
```

```tcsh
# tcsh
eval `python3 ~/src/thebleep/thebleep/__main__.py --alias-loader`
```

A tcsh alias is itself single-quoted and cannot contain a quote, so a checkout
at a path with a space in it cannot be written into one; it says so and falls
back, and `THEBLEEP_COMMAND` is how you tell it what to run instead. Every other
shell handles such a path.

Otherwise the path is the only thing to change. It works from any directory, needs no
`PYTHONPATH`, and does not care what else is installed — the alias it writes
names that interpreter and that checkout, so what your shell runs is the working
tree in front of you. If `pip install --user` is refused on your system
([PEP 668](https://peps.python.org/pep-0668/)), point the line at a virtual
environment's `python3` instead; it is the interpreter in the alias that has to
find `psutil`, and nothing says it must be the system one.

Worth knowing if you develop it: run `thebleep --alias` and you get an alias
that says `thebleep`, which is whatever is on your `PATH` — quite possibly a
release you installed months ago. Run it *as the package*, the way above, and
the alias points back at the clone. `thebleep --doctor` prints which copy is
answering, and is the fastest way to catch the mix-up.

`THEBLEEP_COMMAND` overrides what goes into the alias, for a wrapper of your own
or a shell whose quoting is not the quoting used here:

```bash
export THEBLEEP_COMMAND="/opt/py/bin/python3 /opt/thebleep/thebleep/__main__.py"
```

Prefer a command on your `PATH`? `sh install.sh --dev`, run from the clone,
installs it editable with `uv`, `pipx` or `pip` — same effect, and `thebleep`
becomes a real command.

### The alias, and why it costs nothing

Append the *loader* to your `.bashrc`, `.zshrc` or other startup script, once:

```bash
thebleep --alias-loader >> ~/.bashrc        # or ~/.zshrc, etc.
```

That writes a few lines of shell that define the alias the first time you use
it, and nothing before — so opening a shell costs nothing at all. It is static:
it does not need regenerating when The Bleep is upgraded, because all it does is
call `thebleep --alias` on first use.

```bash
bleep() {
    eval "$(TB_SHELL=bash thebleep --alias bleep)";
    bleep "$@";
}
```

Any name you like, including the one your fingers already know:

```bash
thebleep --alias-loader BLEEP >> ~/.bashrc   # for Mondays
thebleep --alias-loader fuck >> ~/.bashrc
```

### Paying at startup instead

`eval $(thebleep --alias)` in your startup file does the same job by starting a
Python interpreter every time you open a shell, which is the 29 ms in the table
above. Use it if you prefer it, and for the experimental instant mode, which has
to set your prompt up front.

### Your shell

`--alias-loader` writes the right thing for the shell you run it from, so the
only difference between shells is the file it goes in:

| Shell | |
| --- | --- |
| Bash | `thebleep --alias-loader >> ~/.bashrc` |
| Zsh | `thebleep --alias-loader >> ~/.zshrc` |
| Fish | `thebleep --alias-loader >> ~/.config/fish/config.fish` |
| tcsh | `thebleep --alias-loader >> ~/.cshrc` |
| Nushell | `thebleep --alias-loader >> ~/.config/nushell/config.nu` |
| PowerShell | `thebleep --alias-loader >> $profile` |

The few things worth knowing per shell:

- **Bash.** A login shell reads `~/.bash_profile` and not `~/.bashrc`, which is
  how macOS's Terminal starts one. If the alias is not there in a new window,
  that is why; `thebleep --alias-loader >> ~/.bash_profile` as well, or source
  one from the other.
- **Zsh.** `~/.zshrc`, and that is all. If you use a framework that rewrites it,
  put the line in `~/.zshrc.local` or wherever it tells you to.
- **Fish.** `~/.config/fish/config.fish`. Fish is asked for your aliases and
  functions by running `fish -ic`, so an alias defined only for interactive use
  is still found; the answer is cached against `config.fish`, so it is looked up
  again when you change it.
- **tcsh.** `~/.tcshrc` if you have one, `~/.cshrc` otherwise.
- **Nushell.** `$XDG_CONFIG_HOME/nushell/config.nu` if that is set — on every
  platform, which is the order Nushell itself reads them in — otherwise
  `~/.config/nushell/config.nu`, `%APPDATA%\nushell` on Windows or
  `~/Library/Application Support/nushell` on macOS. `thebleep --doctor` tells
  you which one it found. Here `--alias-loader`
  writes the alias itself rather than a stub that fetches it, because Nushell
  has no `eval` to define a command from a string — which costs nothing, since
  what your shell then reads at startup is a dozen lines of Nushell rather than
  a Python interpreter. Nushell 0.87 or newer, for `commandline edit`.
  [What a correction does there](#nushell).
- **PowerShell.** `$profile` may not exist yet:
  `New-Item -Force -Path $profile` first. If PowerShell refuses to run the
  profile, that is the execution policy rather than us:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Both Windows PowerShell
  5.1 and PowerShell 7 work; a chained correction is written as
  `first; if ($?) { second }`, because `&&` needs 7.
- **Anything else** gets a generic alias that reads your last command with
  `fc -ln -1`. Rules that need to know which shell you are in will not; set
  `TB_SHELL` yourself if it guesses wrong.

Without an alias to tell it, *The Bleep* works out which shell it is in by
walking up the process tree — which is right almost always, and wrong in the
places where the process above it is not the shell: a container, an IDE's
integrated terminal, a wrapper script, `distrobox`. `--shell` says so outright:

```bash
thebleep --shell fish --alias-loader >> ~/.config/fish/config.fish
thebleep --shell bash git brnch          # correct as though bash had asked
```

It takes any of `bash`, `csh`, `fish`, `nu`, `powershell`, `pwsh`, `tcsh`,
`zsh`, and
an unknown name is an error rather than a silent fallback. Naming the shell also
skips the walk up the process tree, so it is the cheaper way round as well as
the certain one.

Changes are only available in a new shell session. To make changes immediately
available, run `source ~/.bashrc` (or your shell config file like `.zshrc`).

To run fixed commands without confirmation, use `--yes` (or `-y` for short):

```bash
bleep --yes
```

To fix commands recursively until succeeding, use the `-r` option:

```bash
bleep -r
```

##### [Back to Contents](#contents)

## Updating

However you installed it:

```bash
uv tool upgrade thebleep
pipx upgrade thebleep
pip install --user --upgrade thebleep
```

Or run the one-liner again, which upgrades in place. The alias line in your
startup file never needs regenerating — all it does is call
`thebleep --alias` the first time you use it.

## Uninstall

Reverse the two steps: delete the *thebleep* line from your shell's startup
file, then remove the package with `uv tool uninstall thebleep`,
`pipx uninstall thebleep` or `pip uninstall thebleep`.

## How it works

*The Bleep* attempts to match the previous command with a rule. If a match is
found, a new command is created using the matched rule and executed.

### Commands with something in front of them

The interesting command is not always the first word:

```bash
$ sudo -u www-data git chekout main
$ bleep
sudo -u www-data git checkout main
```

`sudo`, `doas`, `env FOO=bar`, `command`, `builtin`, `nice`, `nohup`, `setsid`
and `stdbuf` are peeled off — nested, in any combination — the command
underneath is corrected by every rule as though you had typed it on its own,
and the wrapper comes back in front of the suggestion exactly as you wrote it.
That is one model applied to every rule, in place of the `sudo`-only decorator
that 26 of them had to ask for individually — which is still there, and still
works, for rules outside this repository.

It fails towards leaving your command alone. A wrapper that is not transparent
is not peeled: `sudo -i` and `sudo -s` run a shell, `sudo -e` opens an editor,
`sudo -l` lists privileges and `command -v` prints a path, so none of those is
the command underneath in a hat. Neither is an option it does not recognise —
that option might take a value, and mistaking a value for the command is worse
than not offering a correction. Nor is a script with shell syntax in it, where
the first word is not the only command anyway, nor a wrapper whose words would
have to be re-quoted to be handed back. `time`, `strace` and `valgrind` are
transparent and still not peeled, because the output being corrected from is
partly theirs: `time git stauts` prints git's error and `time`'s report, and a
rule that picks a name out of a command's output would offer one of `time`'s
lines as a branch to check out.

The following rules are enabled by default:

* `adb_unknown_command` — fixes misspelled commands like `adb logcta`;
* `ag_literal` — adds `-Q` to `ag` when suggested;
* `aws_cli` — fixes misspelled commands like `aws dynamdb scan`;
* `argparse_invalid_choice` — the same for Python's standard library [argparse](https://docs.python.org/3/library/argparse.html), which is what `pytest`, `mypy`, `pre-commit`, `tox` and `coverage` are built on — `pytest --color=ayt`, `mytool bulid`;
* `az_cli` — fixes misspelled commands like `az providers`;
* `bun_script_not_found` — corrects a mistyped [bun](https://bun.com/) script or command — `bun run buidl`, `bun instal`. bun reports an unknown word as a missing script whether or not `run` was typed, and suggests nothing itself, so the candidates are the project's `package.json` scripts and bun's own commands;
* `cargo` — runs `cargo build` instead of `cargo`;
* `cat_dir` — replaces `cat` with `ls` when you try to `cat` a directory;
* `cd_correction` — spellchecks and corrects failed cd commands;
* `cd_cs` — changes `cs` to `cd`;
* `cd_mkdir` — creates directories before cd'ing into them;
* `cd_parent` — changes `cd..` to `cd ..`;
* `chmod_x` — adds execution bit;
* `clap_suggestion` — corrects a mistyped subcommand **or option** in any tool built with [clap](https://docs.rs/clap/), from the tip clap itself prints — `ruff chekc .`, `uv syncc`, `cargo instal`, `ruff check --fixx`. Not one rule per tool: every clap program is covered, including ones released after this was written. Replaces the hand-written `cargo_no_command` and `uv_unknown_subcommand`;
* `click_suggestion` — the same for [Click](https://click.palletsprojects.com/), which most Python tools use — `black --chekc .`;
* `choco_install` — appends common suffixes for chocolatey packages;
* `cobra_suggestion` — the same for [cobra](https://cobra.dev/), which most Go tools use — `gh reop list`, `helm instal mychart`, `kubectl gat pods`. Replaces the hand-written `kubectl_unknown_command`;
* `commander_suggestion` — the same for [commander.js](https://github.com/tj/commander.js), which most Node.js tools use — `prettier --chekc .`, `mytool bulid`;
* `composer_not_command` — fixes composer command name;
* `conda_mistype` — fixes conda commands;
* `cp_create_destination` — creates a new directory when you attempt to `cp` or `mv` to a non-existent one
* `cp_omitting_directory` — adds `-a` when you `cp` directory;
* `cpp11` — adds missing `-std=c++11` to `g++` or `clang++`;
* `dirty_untar` — suggests re-extracting a `tar x` that unpacked into the current directory into a directory of its own (it does not delete what was already unpacked — nothing in the archive says which of those files you already had);
* `dirty_unzip` — the same for `unzip`;
* `django_south_ghost` — adds `--delete-ghost-migrations` to failed because ghosts django south migration;
* `django_south_merge` — adds `--merge` to inconsistent django south migration;
* `docker_daemon_not_running` — starts Docker with `systemctl` when its daemon is not listening;
* `docker_login` — executes a `docker login` and repeats the previous command;
* `docker_not_command` — fixes wrong docker commands like `docker tags`;
* `docker_image_being_used_by_container` — removes the container that is using the image before removing the image;
* `dry` — fixes repetitions like `git git push`;
* `fab_command_not_found` — fixes misspelled fabric commands;
* `fix_alt_space` — replaces Alt+Space with Space character;
* `fix_file` — opens a file with an error in your `$EDITOR`;
* `gem_unknown_command` — fixes wrong `gem` commands;
* `git_add` — fixes *"pathspec 'foo' did not match any file(s) known to git."*;
* `git_add_force` — adds `--force` to `git add <pathspec>...` when paths are .gitignore'd;
* `git_bisect_usage` — fixes `git bisect strt`, `git bisect goood`, `git bisect rset`, etc. when bisecting;
* `git_branch_delete` — changes `git branch -d` to `git branch -D`;
* `git_branch_delete_checked_out` — when you try to delete the branch you are on, checks out the default branch first and then deletes it: whatever `origin/HEAD` points at, or `main` or `master` if there is no remote to ask;
* `git_branch_exists` — offers `git branch -d foo`, `git branch -D foo` or `git checkout foo` when creating a branch that already exists;
* `git_branch_list` — catches `git branch list` in place of `git branch` and removes created branch;
* `git_branch_0flag` — fixes commands such as `git branch 0v` and `git branch 0r` removing the created branch;
* `git_checkout` — fixes branch name or creates new branch;
* `git_clone_git_clone` — replaces `git clone git clone ...` with `git clone ...`
* `git_clone_missing` — adds `git clone` to URLs that appear to link to a git repository.
* `git_commit_add` — offers `git commit -a ...` or `git commit -p ...` after previous commit if it failed because nothing was staged;
* `git_commit_amend` — offers `git commit --amend` after previous commit;
* `git_commit_reset` — offers `git reset HEAD~` after previous commit;
* `git_diff_no_index` — adds `--no-index` to previous `git diff` on untracked files;
* `git_diff_staged` — adds `--staged` to previous `git diff` with unexpected output;
* `git_dubious_ownership` — adds the repository to `safe.directory` when git refuses to touch it because somebody else owns it;
* `git_fix_stash` — fixes `git stash` commands (misspelled subcommand and missing `save`);
* `git_flag_after_filename` — fixes `fatal: bad flag '...' after filename`
* `git_help_aliased` — fixes `git help <alias>` commands replacing <alias> with the aliased command;
* `git_hook_bypass` — adds `--no-verify` flag previous to `git am`, `git commit`, or `git push` command;
* `git_lfs_mistype` — fixes mistyped `git lfs <command>` commands;
* `git_main_master` — fixes incorrect branch name between `main` and `master`
* `git_merge` — adds remote to branch names;
* `git_merge_unrelated` — adds `--allow-unrelated-histories` when required
* `git_not_command` — fixes wrong git commands like `git brnch`;
* `git_pull` — sets upstream before executing previous `git pull`;
* `git_pull_clone` — clones instead of pulling when the repo does not exist;
* `git_pull_uncommitted_changes` — stashes changes before pulling and pops them afterwards;
* `git_push` — adds `--set-upstream origin $branch` to previous failed `git push`;
* `git_push_different_branch_names` — fixes pushes when local branch name does not match remote branch name;
* `git_push_pull` — runs `git pull` when `push` was rejected;
* `git_push_without_commits` — creates an initial commit if you forget and only `git add .`, when setting up a new project;
* `git_rebase_no_changes` — runs `git rebase --skip` instead of `git rebase --continue` when there are no changes;
* `git_remote_delete` — replaces `git remote delete remote_name` with `git remote remove remote_name`;
* `git_rm_local_modifications` — adds `-f` or `--cached` when you try to `rm` a locally modified file;
* `git_rm_recursive` — adds `-r` when you try to `rm` a directory;
* `git_rm_staged` —  adds `-f` or `--cached` when you try to `rm` a file with staged changes
* `git_rebase_merge_dir` — offers `git rebase (--continue | --abort | --skip)` or removing the `.git/rebase-merge` dir when a rebase is in progress;
* `git_remote_seturl_add` — runs `git remote add` when `git remote set_url` on nonexistent remote;
* `git_stash` — stashes your local modifications before rebasing or switching branch;
* `git_stash_pop` — adds your local modifications before popping stash, then resets;
* `git_tag_force` — adds `--force` to `git tag <tagname>` when the tag already exists;
* `git_unknown_subcommand` — reads the list git prints for a mistyped second word, like `git remote ad`;
* `git_two_dashes` — adds a missing dash to commands like `git commit -amend` or `git rebase -continue`;
* `go_run` — appends `.go` extension when compiling/running Go programs;
* `go_unknown_command` — fixes wrong `go` commands, for example `go bulid`;
* `gradle_no_task` — fixes not found or ambiguous `gradle` task;
* `gradle_wrapper` — replaces `gradle` with `./gradlew`;
* `grep_arguments_order` — fixes `grep` arguments order for situations like `grep -lir . test`;
* `grep_recursive` — adds `-r` when you try to `grep` directory;
* `grunt_task_not_found` — fixes misspelled `grunt` commands;
* `gulp_not_task` — fixes misspelled `gulp` tasks;
* `has_exists_script` — prepends `./` when script/binary exists;
* `heroku_multiple_apps` — adds `--app <app>` to `heroku` commands like `heroku pg`;
* `heroku_not_command` — fixes wrong `heroku` commands like `heroku log`;
* `history` — tries to replace command with the most similar command from history;
* `hostscli` — tries to fix `hostscli` usage;
* `ifconfig_device_not_found` — fixes wrong device names like `wlan0` to `wlp2s0`;
* `invalid_argument_for_option` — offers the values a tool listed after refusing one, like `ls --sort=nmae`;
* `java` — removes `.java` extension when running Java programs;
* `javac` — appends missing `.java` when compiling Java files;
* `lein_not_task` — fixes wrong `lein` tasks like `lein rpl`;
* `long_form_help` — changes `-h` to `--help` when the short form version is not supported
* `ln_no_hard_link` — catches hard link creation on directories, suggest symbolic link;
* `ln_s_order` — fixes `ln -s` arguments order;
* `ls_all` — adds `-A` to `ls` when output is empty;
* `ls_lah` — adds `-lah` to `ls`;
* `man` — changes manual section;
* `man_no_space` — fixes man commands without spaces, for example `mandiff`;
* `mercurial` — fixes wrong `hg` commands;
* `misplaced_space` — fixes a command split in the wrong place, like `sud osu` for `sudo su`;
* `missing_space_before_known_subcommand` — fixes a missing space where the rest is a flag or a subcommand the tool listed, like `ls-la` or `gitstatus`;
* `missing_space_before_subcommand` — fixes command with missing space like `npminstall`;
* `mkdir_p` — adds `-p` when you try to create a directory without a parent;
* `mvn_no_command` — adds `clean package` to `mvn`;
* `mvn_unknown_lifecycle_phase` — fixes misspelled life cycle phases with `mvn`;
* `npm_missing_script` — fixes `npm` custom script name in `npm run-script <script>`;
* `npm_run_script` — adds missing `run-script` for custom `npm` scripts;
* `npm_wrong_command` — fixes wrong npm commands like `npm urgrade`;
* `no_command` — fixes wrong console commands, for example `vom/vim`;
* `no_such_file` — creates missing directories with `mv` and `cp` commands;
* `omnienv_no_such_command` — fixes wrong commands for `goenv`, `nodenv`, `pyenv` and `rbenv` (eg.: `pyenv isntall` or `goenv list`);
* `open` — either prepends `http://` to address passed to `open` or creates a new file or directory and passes it to `open`;
* `pip_install` — adds `--user` when `pip install` failed for want of permission. It does not offer `sudo pip install`; where `--user` is not enough, `pip_externally_managed` below has the answer;
* `pip_externally_managed` — offers `pipx` or a virtual environment when pip refuses to install into the system Python (PEP 668);
* `pip_unknown_command` — fixes wrong `pip` commands, for example `pip instatl/pip install`;
* `php_s` — replaces `-s` by `-S` when trying to run a local php server;
* `ping_url` — pings the host in a URL you pasted, not the URL;
* `port_already_in_use` — kills process that bound port;
* `prove_recursively` — adds `-r` when called with directory;
* `python_command` — prepends `python` when you try to run non-executable/without `./` python script;
* `python_execute` — appends missing `.py` when executing Python files;
* `quotation_marks` — fixes uneven usage of `'` and `"` when containing args';
* `path_correction` — spellchecks a path against the filesystem, like `cd_correction` but for any command, for example `cat /ec/passwd` -> `cat /etc/passwd`;
* `path_from_history` — replaces not found path with a similar absolute path from history;
* `rails_migrations_pending` — runs pending migrations;
* `react_native_command_unrecognized` — fixes unrecognized `react-native` commands;
* `remove_shell_prompt_literal` — removes leading shell prompt symbol `$`, common when copying commands from documentations;
* `remove_trailing_cedilla` — removes trailing cedillas `ç`, a common typo for European keyboard layouts;
* `rm_dir` — adds `-r` when you try to remove a directory;
* `scm_correction` — corrects wrong scm like `hg log` to `git log`;
* `sed_unterminated_s` — adds missing '/' to `sed`'s `s` commands;
* `sl_ls` — changes `sl` to `ls`;
* `ssh_known_hosts` — on a host key warning, suggests the `ssh-keygen -R` that ssh itself recommends, in front of your command, so you can see which key it drops before agreeing;
* `sudo` — prepends `sudo` to the previous command if it failed because of permissions;
* `sudo_command_from_user_path` — runs commands from users `$PATH` with `sudo`;
* `switch_lang` — switches command from your local layout to en;
* `systemctl` — correctly orders parameters of confusing `systemctl`;
* `terraform_init` — runs `terraform init` before plan or apply;
* `terraform_no_command` — fixes unrecognized `terraform` commands;
* `test.py` — runs `pytest` instead of `test.py`;
* `touch` — creates missing directories before "touching";
* `tsuru_login` — runs `tsuru login` if not authenticated or session expired;
* `tsuru_not_command` — fixes wrong `tsuru` commands like `tsuru shell`;
* `tmux` — fixes `tmux` commands;
* `unknown_command` — fixes hadoop hdfs-style "unknown command", for example adds missing '-' to the command on `hdfs dfs ls`;
* `unsudo` — removes `sudo` from previous command if a process refuses to run on superuser privilege.
* `vagrant_up` — starts up the vagrant instance;
* `whois` — fixes `whois` command;
* `workon_doesnt_exists` — fixes `virtualenvwrapper` env name os suggests to create new.
* `wrong_hyphen_before_subcommand` — removes an improperly placed hyphen (`apt-install` -> `apt install`, `git-log` -> `git log`, etc.)
* `wp_cli_suggestion` — fixes misspelled `wp` (WP-CLI) commands, like `wp plugn list`;
* `yarn_alias` — fixes aliased `yarn` commands like `yarn ls`;
* `yarn_command_not_found` — fixes misspelled `yarn` commands;
* `yarn_command_replaced` — fixes replaced `yarn` commands;
* `yarn_help` — makes it easier to open `yarn` documentation;

##### [Back to Contents](#contents)

The following rules are enabled by default on specific platforms only:

* `apt_get` — installs app from apt if it not installed (requires `python-commandnotfound` / `python3-commandnotfound`);
* `apt_get_search` — changes trying to search using `apt-get` with searching using `apt-cache`;
* `apt_invalid_operation` — fixes invalid `apt` and `apt-get` calls, like `apt-get isntall vim`;
* `apt_list_upgradable` — helps you run `apt list --upgradable` after `apt update`;
* `apt_upgrade` — helps you run `apt upgrade` after `apt list --upgradable`;
* `brew_cask_dependency` — installs cask dependencies;
* `brew_install` — fixes formula name for `brew install`;
* `brew_reinstall` — turns `brew install <formula>` into `brew reinstall <formula>`;
* `brew_link` — adds `--overwrite --dry-run` if linking fails;
* `brew_uninstall` — adds `--force` to `brew uninstall` if multiple versions were installed;
* `brew_unknown_command` — fixes wrong brew commands, for example `brew docto/brew doctor`;
* `brew_update_formula` — turns `brew update <formula>` into `brew upgrade <formula>`;
* `dnf_no_such_command` — fixes mistyped DNF commands;
* `nixos_cmd_not_found` — installs apps on NixOS;
* `pacman` — installs app with `pacman` if it is not installed (uses `paru`, `yay`, `pikaur` or `yaourt` if available, in that order);
* `option_typo` — fixes a mistyped long option in **any** program: `ls --colour` → `ls --color`, `git status --shrot` → `git status --short`, `curl --verbse` → `curl --verbose`, `tar --extrat` → `tar --extract`. Reads the options out of the program's own usage when it printed them, and asks `<program> --help` only when the program itself invited it (`Try 'ls --help'`);
* `pacman_invalid_option` — replaces lowercase `pacman` options with uppercase.
* `pacman_not_found` — fixes package name with `pacman`, `paru`, `yay`, `pikaur` or `yaourt`.
* `yum_invalid_operation` — fixes invalid `yum` calls, like `yum isntall vim`;
* `zypper_no_such_command` — fixes mistyped `zypper` commands and their abbreviations on openSUSE and SLE, like `zypper isntall vim` or `zypper dpu`.

The following commands are bundled with *The Bleep*, but are not enabled by
default:

* `git_push_force` — adds `--force-with-lease` to a `git push` (may conflict with `git_push_pull`);
* `python_module_error` — installs the package a missing import needs. An import name is not a distribution name (`import yaml` wants PyYAML, `cv2` wants opencv-python), and a mistyped import makes the suggestion `pip install <typo>`, so this is not on by default;
* `rm_root` — adds `--no-preserve-root` to `rm -rf /` command.

##### [Back to Contents](#contents)

## Creating your own rules

To add your own rule, create a file named `your-rule-name.py`
in `~/.config/thebleep/rules`. The rule file must contain two functions:

```python
match(command: Command) -> bool
get_new_command(command: Command) -> str | list[str]
```

Rules can also contain the optional variables `enabled_by_default`,
`requires_output` and `priority`.

`Command` has three attributes: `script`, `output` and `script_parts`.
Your rule should not change `Command`.


**Rules api changed in 3.0:** To access a rule's settings, import it with
 `from thebleep.conf import settings`

`settings` is a special object assembled from `~/.config/thebleep/settings.py`,
and values from env ([see more below](#settings)).

A whole rule, for a `kubectl` that wants `--namespace` and did not get one:

```python
import re

# Read out of the rule by the loader, so a `kubectl` rule is never even
# compiled for your `git push`. Worth declaring; see How it works.
from thebleep.utils import for_app


@for_app('kubectl')
def match(command):
    return 'the server doesn\'t have a resource type' in command.output


def get_new_command(command):
    return re.sub(r'^kubectl ', 'kubectl --namespace default ', command.script)


# All optional, and these are the defaults.
enabled_by_default = True
requires_output = True    # do not even try me without the command's output
priority = 1000           # lower is matched first
```

That is the whole interface. A rule reads a command and returns a string — or a
list of strings, to offer several — and the one you accept is the one that runs.

### side_effect, and why to think twice

A rule may also define:

```python
side_effect(old_command: Command, fixed_command: str) -> None
```

which runs after you accept the correction, and only then — pressing
<kbd>tab</kbd> to [edit](#edit-before-you-run) does not fire it, because nothing
has run. It is supported and is not going away, and third-party rules that use it
keep working.

It is still the wrong tool nine times out of ten. Whatever it does happens
*outside* the command you were shown and agreed to, so the thing you approved is
not the thing that happened — which is exactly how `dirty_untar` came to delete
files and `ssh_known_hosts` came to drop a host key behind a warning you never
read. Both are now rules that say what they do in the command itself, and both
are better rules for it. Prefer `shell.and_('the thing you want first',
command.script)`: it is visible, it is refusable, and it appears in your history
like anything else you ran.

[More examples of rules](thebleep/rules),
[utility functions for rules](thebleep/utils.py),
[app/os-specific helpers](thebleep/specific/).

##### [Back to Contents](#contents)

## Settings

Several *The Bleep* parameters can be changed in the file `$XDG_CONFIG_HOME/thebleep/settings.py`
(`$XDG_CONFIG_HOME` defaults to `~/.config`):

* `rules` — list of enabled rules, by default `thebleep.const.DEFAULT_RULES`;
* `exclude_rules` — list of disabled rules, by default `[]`;
* `require_confirmation` — requires confirmation before running new command, by default `True`;
  when there's no terminal attached (a pipe, a subprocess or CI) confirmation is impossible,
  so the suggestion is only printed and nothing is run — pass `--yes` to apply it;
* `confirm_replay` — asks before running your previous command a second time to read
  what it printed, by default `True`; see [Reading the previous command](#reading-the-previous-command);
* `wait_command` — the max amount of time in seconds for getting previous command output;
* `no_colors` — disable colored output;
* `priority` — dict with rules priorities, rule with lower `priority` will be matched first;
* `debug` — enables debug output, by default `False`;
* `history_limit` — the numeric value of how many history commands will be scanned, like `2000`;
* `alter_history` — push fixed command to history, by default `True`;
* `wait_slow_command` — max amount of time in seconds for getting previous command output if it in `slow_commands` list;
* `slow_commands` — list of slow commands;
* `num_close_matches` — the maximum number of close matches to suggest, by default `3`;
* `excluded_search_path_prefixes` — path prefixes to ignore when searching for commands, by default `[]`;
* `instant_mode` — read what scrolled past instead of running your command again, by default `False`; see [Experimental instant mode](#experimental-instant-mode);
* `repeat` — if the corrected command fails too, correct that as well, by default `False`; `--repeat` does it for one run;
* `edit` — hand the correction to your command line to edit instead of running it, by default `False`; `--edit` does it for one run, and <kbd>tab</kbd> does it for one suggestion; see [Edit before you run](#edit-before-you-run);
* `explain` — say which rule made each suggestion and what it matched, by default `False`; `--explain` does it for one run, and <kbd>?</kbd> does it at the prompt; see [Why am I being told this](#why-am-i-being-told-this);
* `env` — environment variables to set for your previous command when it is run again to read its output, by default `{'LC_ALL': 'C', 'LANG': 'C'}`, which is there so that rules can look for English error messages. Git also gets `GIT_TRACE=1`, so that `git st` can be resolved to whatever alias it stands for; nothing else does.

An example of `settings.py`:

```python
rules = ['sudo', 'no_command']
exclude_rules = ['git_push']
require_confirmation = True
confirm_replay = True
wait_command = 10
no_colors = False
priority = {'sudo': 100, 'no_command': 9999}
debug = False
history_limit = 9999
wait_slow_command = 20
slow_commands = ['react-native', 'gradle']
num_close_matches = 5
instant_mode = False
repeat = False
edit = False
explain = False
env = {'LC_ALL': 'C', 'LANG': 'C'}
```

Or via environment variables:

* `THEBLEEP_RULES` — list of enabled rules, like `DEFAULT_RULES:rm_root` or `sudo:no_command`;
* `THEBLEEP_EXCLUDE_RULES` — list of disabled rules, like `git_pull:git_push`;
* `THEBLEEP_REQUIRE_CONFIRMATION` — require confirmation before running new command, `true/false`;
* `THEBLEEP_CONFIRM_REPLAY` — ask before running your previous command again to read its output, `true/false`;
* `THEBLEEP_WAIT_COMMAND` — the max amount of time in seconds for getting previous command output;
* `THEBLEEP_NO_COLORS` — disable colored output, `true/false`;
* `THEBLEEP_PRIORITY` — priority of the rules, like `no_command=9999:apt_get=100`,
rule with lower `priority` will be matched first;
* `THEBLEEP_DEBUG` — enables debug output, `true/false`;
* `THEBLEEP_HISTORY_LIMIT` — how many history commands will be scanned, like `2000`;
* `THEBLEEP_ALTER_HISTORY` — push fixed command to history `true/false`;
* `THEBLEEP_WAIT_SLOW_COMMAND` — the max amount of time in seconds for getting previous command output if it in `slow_commands` list;
* `THEBLEEP_SLOW_COMMANDS` — list of slow commands, like `lein:gradle`;
* `THEBLEEP_NUM_CLOSE_MATCHES` — the maximum number of close matches to suggest, like `5`.
* `THEBLEEP_REPEAT` — if the corrected command fails too, correct that as well, `true/false`.
* `THEBLEEP_EDIT` — hand the correction to your command line to edit instead of running it, `true/false`.
* `THEBLEEP_EXPLAIN` — say which rule made each suggestion and what it matched, `true/false`.
* `THEBLEEP_INSTANT_MODE` — read what scrolled past instead of running your command again, `true/false`; see [Experimental instant mode](#experimental-instant-mode).
* `THEBLEEP_EXCLUDED_SEARCH_PATH_PREFIXES` — path prefixes to ignore when searching for commands, by default `[]`.

For example:

```bash
export THEBLEEP_RULES='sudo:no_command'
export THEBLEEP_EXCLUDE_RULES='git_pull:git_push'
export THEBLEEP_REQUIRE_CONFIRMATION='true'
export THEBLEEP_WAIT_COMMAND=10
export THEBLEEP_NO_COLORS='false'
export THEBLEEP_PRIORITY='no_command=9999:apt_get=100'
export THEBLEEP_HISTORY_LIMIT='2000'
export THEBLEEP_NUM_CLOSE_MATCHES='5'
```

##### [Back to Contents](#contents)

## Third-party packages with rules

If you'd like to make a specific set of non-public rules, but would still like
to share them with others, create a package named `thebleep_contrib_*` with
the following structure:

```
thebleep_contrib_foo
  thebleep_contrib_foo
    rules
      __init__.py
      *third-party rules*
    __init__.py
    *third-party-utils*
  setup.py
```

*The Bleep* will find rules located in the `rules` module.

##### [Back to Contents](#contents)

## Experimental instant mode

Correcting a command means knowing what it printed, which normally means running
it again — the reason *The Bleep*
[asks first](#reading-the-previous-command). Instant mode takes the other way
out: it records your session with [script](https://en.wikipedia.org/wiki/Script_(Unix))
as it happens and reads the log, so the previous command never runs twice and
the question never comes up. It is the better answer where it works, and it is
also the faster one.

Currently, instant mode only supports bash and zsh. zsh's autocorrect function also needs to be disabled in order for thebleep to work properly.

To enable instant mode, add `--enable-experimental-instant-mode`
to the alias initialization in `.bashrc`, `.bash_profile` or `.zshrc`.

For example:

```bash
eval $(thebleep --alias --enable-experimental-instant-mode)
```

### What it does, and where it stops

It is called experimental because it is, and it is worth being specific about
which parts. This is what a real terminal was driven through, on bash 5.2 and
zsh 5.9:

| | |
| --- | --- |
| A correction with no rerun and no question | works |
| After <kbd>ctrl+c</kbd>, or a window resize | works |
| Unicode in the output | works |
| Megabytes of output, wrapping the recording several times | works |
| Megabytes of Unicode output, wrapping mid-character | works |
| Output that was never text at all (a `cat` of a binary) | works |
| After a full-screen program (`less`, `vim`, `top`) | **does not correct** |
| After a shell started inside the shell | **does not correct** |

The two Unicode rows are one row in the tests and were two bugs until this
release: the recording is a ring, so reading the last megabyte of it begins at
whatever byte is a megabyte back, and that is inside a character as often as the
output has multibyte characters in it. Decoding it raised, and the traceback came
out of the middle of a correction.
[`tests/output_readers/test_read_log.py`](tests/output_readers/test_read_log.py)
holds every offset into that seam.

The last two rows are the same limitation. What is recorded is the raw terminal
stream, and where one command's output ends is worked out by looking for a mark
that instant mode puts in your `PS1`. A program that takes over the screen moves
the cursor wherever it likes and the marks stop lining up with what is on it; a
nested shell writes a second set of them. For the same reason it needs your
`PS1` to still contain that mark, so a prompt framework that rebuilds `PS1`
after the alias is set up — powerlevel10k, starship, some oh-my-zsh themes —
switches instant mode off, with a warning saying so.

Where it does not work it does not go wrong: the mark is missing, or the command
has scrolled out of the recording, and instant mode is simply not in play for
that correction — which takes the ordinary route and
[asks before it runs anything again](#reading-the-previous-command). Falling back
gains nothing: the question is the same question, and the same short list of
programs that only ever read is what skips it.

What is fixed rather than documented:

- **The recording is yours alone.** It used to be created world-readable in
  `/tmp` — a megabyte of everything that had scrolled past, which is the
  contents of every file you read, every token a command printed, and every
  password typed at a prompt that echoes. It is mode 0600 now, in
  `$XDG_RUNTIME_DIR` where there is one, created with `O_EXCL` and `O_NOFOLLOW`
  so a name somebody else got to first is refused rather than opened.
- **It goes when the session goes.** Closing the terminal used to leave the
  recording, the logger and the shell inside it running for the rest of the
  login session. The logger removes its own recording on the way out however it
  leaves, and the shell that started it has a `trap` as a backstop for
  `SIGKILL`.
- **No more holes in it.** When the recording filled up, the chunk that
  overflowed was dropped rather than written after the room was made, so a busy
  session lost up to a kilobyte of output every time it wrapped.
- **The terminal is put back.** A shell that exited normally used to leave your
  terminal in raw mode.

##### [Back to Contents](#contents)

## Performance

The numbers are [at the top](#why-not-just-the-fuck), and they are meant to be
checked rather than believed. Same machine, same Python, 30 runs each, medians,
measured with the harness in [`bench/`](bench/README.md); the run they come from
is committed as [`bench/results/final.json`](bench/results/final.json), and the
chart at the top is written from that file by
[`bench/chart.py`](bench/chart.py), so the two cannot drift apart.

The shell startup row is the eager alias, `eval "$(thebleep --alias)"`, which
starts an interpreter every time you open a shell. The loader is the row that is
not in the table, because there is nothing to time: it is five lines of shell
that define a function, and the interpreter starts the first time you use the
alias instead. Timing it against a shell with nothing configured at all comes out
inside the run-to-run spread of shell startup, which is the honest answer rather
than a number.

Reproduce it yourself:

```bash
./bench/setup_subjects.sh python3.11      # builds both, from their own packages
BENCH_CPU=2,3 ./bench/bench.py --runs 30 \
    --subject fuck=bench/.venvs/fuck-3.11/bin/thefuck \
    --subject bleep=bench/.venvs/bleep-3.11/bin/thebleep
```

Python 3.11 is used for the comparison because *The Fuck* cannot start on 3.12
or newer — it imports `distutils`, which is no longer in the standard library.
On this machine the interpreter itself costs 9 ms before either app runs a line,
so that is the floor both are measured against. The `environment` block in the
result file records the commit it was measured at, the kernel, the CPU and the
harness's interpreter, so `git show` is what says which source those numbers
belong to.

Where the time went:

- **Rules are compiled once, not on every command.** The compiled rules live in
  a cache keyed by the interpreter and the rule files' timestamps.
- **Most rules are never loaded.** A rule that declares `@for_app('git', ...)`,
  or whose match needs a particular string in the output, cannot match your
  `brew install` — and that is readable from the rule's syntax tree without
  running it. A typical command now reaches about a fifth of the 186 rules, and
  one for a tool with many rules of its own — `git` — under a quarter, instead of
  all of them. Rules that don't say what they are about are always loaded, so
  this makes corrections faster, never fewer.
  [`tests/test_performance.py`](tests/test_performance.py) fails if dispatch
  goes broad again.
- **Startup imports almost nothing, and so does a correction.** `pyte`,
  `psutil`, `argparse`, `pprint` and the five shells you are not using never
  arrive at all; `ast`, `pickle`, `socket`, `uuid`, `tempfile`, `shutil`,
  `subprocess`, `difflib` and `ctypes` arrive only on the paths that use them —
  roughly half of what a correction used to open.
  [`tests/test_performance.py`](tests/test_performance.py) names every module
  that has to stay out and holds the total to a budget, measured on whatever
  machine it is running on: the absolute count depends on the interpreter and on
  how the package was installed, so it is a test rather than a number here.
  This matters most on Windows, where every module is a file a virus scanner
  reads before the interpreter may map it.
- **The failed command's output is read while it runs.** It used to be read
  after the command exited, which deadlocks as soon as the output fills the
  pipe buffer: anything printing more than about 64KB waited out the full
  timeout and then produced *nothing to correct from*. That is the 28.4× row
  above, and it is a correctness fix as much as a speed one.
- **Nothing is scanned twice.** The list of everything on your `$PATH` is
  remembered until a directory on it changes.

If a cache ever gets in your way, `thebleep --clear-cache` removes them all,
and `THEBLEEP_NO_RULE_PACK=true` turns the rule cache off entirely.

### On Windows

*The Fuck* has been called slow on Windows for years, and the reason is not
either tool's own logic. Windows charges for *opening files*, and a Python module
is a file the interpreter has to find and then open — with a virus scanner reading
it first. So the work was to open fewer of them, which is the module list above,
and it is the change that matters most here.

There are no numbers in this section, and that is deliberate. The Linux table at
the top comes from a committed result file with the machine, the kernel, the CPU,
the interpreter and the source commit recorded in it, produced by a harness in
this repository that anybody can run. Nothing equivalent exists for Windows: the
GitHub runner is Windows Server rather than a desktop with Defender in its
default configuration, and a figure measured once on somebody's laptop with no
artifact behind it is marketing rather than evidence. If you would like the same
table for Windows, [`bench/bench.py`](bench/bench.py) runs there —
[`bench/README.md`](bench/README.md) says how — and a recorded run would be a
welcome pull request.

What *is* checked on Windows, on every push: the whole test suite on Python 3.9
through 3.14, and the correction loop end to end in real Windows PowerShell 5.1
and PowerShell 7, because the two do not agree about command chaining. The
import budget in [`tests/test_performance.py`](tests/test_performance.py) is
enforced there as well as everywhere else, which is what stops the thing that
made it slow from coming back.

Two costs are left, and neither belongs to either tool: an interpreter takes
several times longer to start on Windows than on Linux, and the failed command
still has to be run a second time to see what it printed. Both tools pay both.

##### [Back to Contents](#contents)

## Developing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License MIT
Project License can be found [here](LICENSE.md).


[version-badge]:   https://img.shields.io/badge/version-4.0.4-007EC7.svg
[version-link]:    CHANGELOG.md
[workflow-badge]:  https://github.com/stamparm/thebleep/actions/workflows/test.yml/badge.svg
[workflow-link]:   https://github.com/stamparm/thebleep/actions/workflows/test.yml
[license-badge]:   https://img.shields.io/badge/license-MIT-007EC7.svg

##### [Back to Contents](#contents)
