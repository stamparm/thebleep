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
Open a shell                     ███▋░░░░░░░░░░░░░░    213 ms      43 ms    4.9×
Correct a mistyped command       ████▊░░░░░░░░░░░░░    255 ms      67 ms    3.8×
Correct inside a git repository  ████▎░░░░░░░░░░░░░    249 ms      59 ms    4.2×
Correct when nothing matches     ████▎░░░░░░░░░░░░░    332 ms      77 ms    4.3×
Correct a slow command *         ████████████▍░░░░░    823 ms     564 ms    1.5×
Correct after 1 MB of output     ▊░░░░░░░░░░░░░░░░░    3.25 s     131 ms   24.8×
```
<!-- end benchmark -->

\* that command sleeps for half a second. Both tools have to sit through it to
read what it printed, so this row is mostly the sleep.

Opening a shell is worth a second look: that row is `eval "$(thebleep --alias)"`
in your rc. Use the loader instead and it costs **0.07 ms** — measured against an
empty `bash -c true` on the same machine — because then opening a shell defines a
shell function and runs no Python at all.

The harness is [`bench/`](bench/README.md), the run these numbers come from is
[`bench/results/final.json`](bench/results/final.json), and the block above is
written from that file by [`bench/chart.py`](bench/chart.py). [Reproduce it, and
read where the time went](#performance).

The rest of the reasons:

- **Python 3.9 through 3.14**, tested on Linux, macOS and Windows on every one
  of them — and Bash, Zsh, Fish, tcsh and PowerShell as before.
- **29 issues from *The Fuck*'s backlog are fixed here** — three of them
  command injections — plus the rules that had rotted against current
  `git`, `npm`, `docker`, `cargo`, `brew`, `gem`, `az`, `gradle` and
  `terraform`. [What's fixed](#whats-fixed).
- **It asks before running your previous command a second time.** Reading what
  your command printed used to mean running it again, side effects and all.
  [Safe by default](#safe-by-default).
- **Nothing to relearn.** Same rules, same settings, same `fuck` alias if you
  want it. [Coming from The Fuck](#coming-from-the-fuck).

*The Bleep* is based on the original codebase by Vladimir Iakovlev and its
contributors; their work and history remain fully credited.

## Contents

1. [Safe by default](#safe-by-default)
2. [Coming from The Fuck](#coming-from-the-fuck)
3. [What's fixed](#whats-fixed)
4. [Supported everything](#supported-everything)
5. [Installation](#installation)
6. [Updating](#updating)
7. [How it works](#how-it-works)
8. [Creating your own rules](#creating-your-own-rules)
9. [Settings](#settings)
10. [Third-party packages with rules](#third-party-packages-with-rules)
11. [Experimental instant mode](#experimental-instant-mode)
12. [Performance](#performance)
13. [Developing](#developing)
14. [License](#license-mit)

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

So it asks first. It skips asking in two cases: the program is not there to be
found, so nothing runs either time (`gti status`), or the program is one of a
short list that only ever read, whatever they are asked to do (`ls`, `cat`,
`grep`). That second one is a judgement about the *name*, and a name is not a
proof about the program a `PATH` lookup will find — what makes it a reasonable
one is that the same program under the same name ran a moment ago, when you
typed it. It is deliberately *not* a list of dangerous commands: such a list
only declares the ones nobody thought of to be safe.

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
- One behaviour is deliberately different: *The Bleep* asks before running your
  previous command a second time. `confirm_replay = False` in your settings
  restores what you are used to, and
  [Reading the previous command](#reading-the-previous-command) explains why
  you might not want to.

##### [Back to Contents](#contents)

## What's fixed

Every commit that fixes a reported problem names the issue it fixes, so this is
`git log --grep 'nvbn/thefuck#'` rather than a claim in a README. Twenty-nine
upstream issues so far, and the rest found by running the tools.

**It starts on current Python.** `distutils` was removed in 3.12 and *The Fuck*
imports it, so it cannot run there at all; `pkg_resources` and `imp` were going
the same way. All three are gone, Python 2 support went with them, and the
suite runs on 3.9 through 3.14 on Linux, macOS and Windows.
&nbsp;<sub>[#1499](https://github.com/nvbn/thefuck/issues/1499)
[#1610](https://github.com/nvbn/thefuck/issues/1610)
[#1552](https://github.com/nvbn/thefuck/issues/1552)
[#1479](https://github.com/nvbn/thefuck/issues/1479)
[#873](https://github.com/nvbn/thefuck/issues/873)</sub>

**Three ways a command could be turned into a different command.** Text that
came out of the failed command's own output — a filename, a branch, a URL —
was pasted into the correction unquoted, and the `sudo` rule handed a
re-quoted script to `sh -c` as root. All three are quoted now, with tests that
run the result through a real shell and check what the program actually
received.
&nbsp;<sub>[#1531](https://github.com/nvbn/thefuck/issues/1531)
[#1606](https://github.com/nvbn/thefuck/issues/1606)</sub>

**It asks before running your command again.** To correct a command you have to
know what it printed, and a shell keeps no record, so the command is run a
second time — `deploy`, `git push`, `rm`, whatever it was, before you have
agreed to anything. It asks first now, except where there is nothing to run or
the program only ever reads.
&nbsp;<sub>[#1126](https://github.com/nvbn/thefuck/issues/1126)</sub>

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
&nbsp;<sub>[#1600](https://github.com/nvbn/thefuck/issues/1600)
[#1509](https://github.com/nvbn/thefuck/issues/1509)
[#1026](https://github.com/nvbn/thefuck/issues/1026)
[#1040](https://github.com/nvbn/thefuck/issues/1040)
[#1562](https://github.com/nvbn/thefuck/issues/1562)
[#1539](https://github.com/nvbn/thefuck/issues/1539)
[#1355](https://github.com/nvbn/thefuck/issues/1355)
[#1551](https://github.com/nvbn/thefuck/issues/1551)
[#1258](https://github.com/nvbn/thefuck/issues/1258)
[#1209](https://github.com/nvbn/thefuck/issues/1209)
[#1296](https://github.com/nvbn/thefuck/issues/1296)
[#995](https://github.com/nvbn/thefuck/issues/995)
[#1506](https://github.com/nvbn/thefuck/issues/1506)</sub>

**And it is quicker**, which has [a section of its own](#performance).

##### [Back to Contents](#contents)

## Supported everything

| | |
| --- | --- |
| **Python** | 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 |
| **Systems** | Linux, macOS, Windows — every Python on every one of them, on every push |
| **Shells** | Bash, Zsh, Fish, tcsh, PowerShell, and Windows `cmd` |
| **Rules** | 170 of them, for git, docker, npm, yarn, pip, apt, dnf, pacman, brew, cargo, go, gradle, maven, terraform, aws, az, systemctl and the rest |

Bash, Zsh, Fish and tcsh are exercised end to end, in containers, driving a real
terminal: the tests type a wrong command into the shell, type the alias, and
check what the shell then runs. The Python suite covers all six.

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

<a href='#manual-installation' name='manual-installation'>#</a>
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
Python interpreter every time you open a shell, which is the 38 ms in the table
above rather than a third of a millisecond. Use it if you prefer it, and for the
experimental instant mode, which has to set your prompt up front.

### Your shell

`--alias-loader` writes the right thing for the shell you run it from, so the
only difference between shells is the file it goes in:

| Shell | |
| --- | --- |
| Bash | `thebleep --alias-loader >> ~/.bashrc` |
| Zsh | `thebleep --alias-loader >> ~/.zshrc` |
| Fish | `thebleep --alias-loader >> ~/.config/fish/config.fish` |
| tcsh | `thebleep --alias-loader >> ~/.cshrc` |
| PowerShell | `thebleep --alias-loader >> $profile` |

[The shell-specific notes in *The Fuck*'s
wiki](https://github.com/nvbn/thefuck/wiki/Shell-aliases) still apply too, with
`thefuck` replaced by `thebleep`.

Changes are only available in a new shell session. To make changes immediately
available, run `source ~/.bashrc` (or your shell config file like `.zshrc`).

To run fixed commands without confirmation, use the `--yeah` option (or just `-y` for short, or `--hard` if you're especially frustrated):

```bash
bleep --yeah
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
found, a new command is created using the matched rule and executed. The
following rules are enabled by default:

* `adb_unknown_command` — fixes misspelled commands like `adb logcta`;
* `ag_literal` — adds `-Q` to `ag` when suggested;
* `aws_cli` — fixes misspelled commands like `aws dynamdb scan`;
* `az_cli` — fixes misspelled commands like `az providers`;
* `cargo` — runs `cargo build` instead of `cargo`;
* `cargo_no_command` — fixes wrong commands like `cargo buid`;
* `cat_dir` — replaces `cat` with `ls` when you try to `cat` a directory;
* `cd_correction` — spellchecks and corrects failed cd commands;
* `cd_cs` — changes `cs` to `cd`;
* `cd_mkdir` — creates directories before cd'ing into them;
* `cd_parent` — changes `cd..` to `cd ..`;
* `chmod_x` — adds execution bit;
* `choco_install` — appends common suffixes for chocolatey packages;
* `composer_not_command` — fixes composer command name;
* `conda_mistype` — fixes conda commands;
* `cp_create_destination` — creates a new directory when you attempt to `cp` or `mv` to a non-existent one
* `cp_omitting_directory` — adds `-a` when you `cp` directory;
* `cpp11` — adds missing `-std=c++11` to `g++` or `clang++`;
* `dirty_untar` — suggests re-extracting a `tar x` that unpacked into the current directory into a directory of its own (it does not delete what was already unpacked — nothing in the archive says which of those files you already had);
* `dirty_unzip` — the same for `unzip`;
* `django_south_ghost` — adds `--delete-ghost-migrations` to failed because ghosts django south migration;
* `django_south_merge` — adds `--merge` to inconsistent django south migration;
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
* `git_branch_delete_checked_out` — changes `git branch -d` to `git checkout master && git branch -D` when trying to delete a checked out branch;
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
* `pip_install` — fixes permission issues with `pip install` commands by adding `--user` or prepending `sudo` if necessary;
* `pip_unknown_command` — fixes wrong `pip` commands, for example `pip instatl/pip install`;
* `php_s` — replaces `-s` by `-S` when trying to run a local php server;
* `port_already_in_use` — kills process that bound port;
* `prove_recursively` — adds `-r` when called with directory;
* `python_command` — prepends `python` when you try to run non-executable/without `./` python script;
* `python_execute` — appends missing `.py` when executing Python files;
* `quotation_marks` — fixes uneven usage of `'` and `"` when containing args';
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
* `pacman` — installs app with `pacman` if it is not installed (uses `yay`, `pikaur` or `yaourt` if available);
* `pacman_invalid_option` — replaces lowercase `pacman` options with uppercase.
* `pacman_not_found` — fixes package name with `pacman`, `yay`, `pikaur` or `yaourt`.
* `yum_invalid_operation` — fixes invalid `yum` calls, like `yum isntall vim`;

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

Additionally, rules can contain optional functions:

```python
side_effect(old_command: Command, fixed_command: str) -> None
```
Rules can also contain the optional variables `enabled_by_default`, `requires_output` and `priority`.

`Command` has three attributes: `script`, `output` and `script_parts`.
Your rule should not change `Command`.


**Rules api changed in 3.0:** To access a rule's settings, import it with
 `from thebleep.conf import settings`

`settings` is a special object assembled from `~/.config/thebleep/settings.py`,
and values from env ([see more below](#settings)).

A simple example rule for running a script with `sudo`:

```python
def match(command):
    return ('permission denied' in command.output.lower()
            or 'EACCES' in command.output)


def get_new_command(command):
    return 'sudo {}'.format(command.script)

# Optional:
enabled_by_default = True

def side_effect(command, fixed_command):
    subprocess.call('chmod 777 .', shell=True)

priority = 1000  # Lower first, default is 1000

requires_output = True
```

[More examples of rules](https://github.com/stamparm/thebleep/tree/master/thebleep/rules),
[utility functions for rules](https://github.com/stamparm/thebleep/tree/master/thebleep/utils.py),
[app/os-specific helpers](https://github.com/stamparm/thebleep/tree/master/thebleep/specific/).

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
* `num_close_matches` — the maximum number of close matches to suggest, by default `3`.
* `excluded_search_path_prefixes` — path prefixes to ignore when searching for commands, by default `[]`.

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

##### [Back to Contents](#contents)

## Performance

The numbers are [at the top](#why-not-just-the-fuck), and they are meant to be
checked rather than believed. Same machine, same Python, 30 runs each, medians,
measured with the harness in [`bench/`](bench/README.md); the run they come from
is committed as [`bench/results/final.json`](bench/results/final.json), and the
chart at the top is written from that file by
[`bench/chart.py`](bench/chart.py), so the two cannot drift apart.

The shell startup row is not a typo: with the loader pasted into your rc, a
shell takes 2.5 ms to start against 2.2 ms with nothing configured at all, so
what The Bleep costs you there is a third of a millisecond.

Reproduce it yourself:

```bash
./bench/setup_subjects.sh python3.11      # builds both, from their own packages
BENCH_CPU=2,3 ./bench/bench.py \
    --subject fuck=bench/.venvs/fuck-3.11/bin/thefuck \
    --subject bleep=bench/.venvs/bleep-3.11/bin/thebleep
```

Python 3.11 is used for the comparison because *The Fuck* cannot start on 3.12
or newer — it imports `distutils`, which is no longer in the standard library.
On this machine the interpreter itself costs 11 ms before either app runs a
line, so that is the floor both are measured against.

Where the time went:

- **Rules are compiled once, not on every command.** The compiled rules live in
  a cache keyed by the interpreter and the rule files' timestamps.
- **Most rules are never loaded.** A rule that declares `@for_app('git', ...)`,
  or whose match needs a particular string in the output, cannot match your
  `brew install` — and that is readable from the rule's syntax tree without
  running it. A typical command now reaches around 30 of the 170 rules instead
  of all of them. Rules that don't say what they are about are always loaded,
  so this makes corrections faster, never fewer.
- **Startup imports almost nothing.** `pyte`, `psutil`, `argparse`, `pprint`
  and the five shells you are not using are imported only on the paths that
  need them.
- **The failed command's output is read while it runs.** It used to be read
  after the command exited, which deadlocks as soon as the output fills the
  pipe buffer: anything printing more than about 64KB waited out the full
  timeout and then produced *nothing to correct from*. That is the 24x above,
  and it is a correctness fix as much as a speed one.
- **Nothing is scanned twice.** The list of everything on your `$PATH` is
  remembered until a directory on it changes.

If a cache ever gets in your way, `thebleep --clear-cache` removes them all,
and `THEBLEEP_NO_RULE_PACK=true` turns the rule cache off entirely.

##### [Back to Contents](#contents)

## Developing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License MIT
Project License can be found [here](LICENSE.md).


[version-badge]:   https://img.shields.io/badge/version-4.0.0-007EC7.svg
[version-link]:    CHANGELOG.md
[workflow-badge]:  https://github.com/stamparm/thebleep/actions/workflows/test.yml/badge.svg
[workflow-link]:   https://github.com/stamparm/thebleep/actions/workflows/test.yml
[license-badge]:   https://img.shields.io/badge/license-MIT-007EC7.svg

##### [Back to Contents](#contents)
