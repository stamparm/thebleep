# The Bleep [![Version][version-badge]][version-link] [![Build Status][workflow-badge]][workflow-link] [![MIT License][license-badge]](LICENSE.md)

**A fast, maintained successor to [The Fuck](https://github.com/nvbn/thefuck).**

*The Bleep* fixes mistakes in your previous console command, just like *The Fuck*,
but with current Python support, active maintenance, and a much faster hot path.
It is based on the original codebase by Vladimir Iakovlev and its contributors;
their work and history remain fully credited.

[![gif with examples][examples-link]][examples-link]

## Why The Bleep?

The original idea is still great. The implementation just needed to catch up.

Same machine, same Python 3.11, 30 runs each, median timings:

| What you do | The Fuck 3.32 | The Bleep | Improvement |
| --- | ---: | ---: | ---: |
| Open a shell (`--alias` in your rc) | 205 ms | 38 ms | **5.4x** |
| Open a shell (`--alias-loader`) | 205 ms | 0.3 ms | **no Python at startup** |
| Correct a mistyped command | 240 ms | 57 ms | **4.2x** |
| Correct when nothing matches | 336 ms | 72 ms | **4.7x** |
| Correct after 1 MB of output | 3246 ms | 134 ms | **24.2x** |

The benchmark harness and raw result used for these numbers are included in
[`bench/`](bench/README.md) and `bench/results/final.json`. See
[Performance](#performance) for methodology and implementation details.

Other reasons to switch:

- Python **3.9-3.14** support;
- active maintenance of the original rule ecosystem;
- much lower shell-startup overhead;
- faster rule dispatch and executable lookup;
- large command output no longer deadlocks the correction path;
- Bash, Zsh, Fish, tcsh and Windows shell support inherited and maintained;
- you can still use `fuck` as your alias if you prefer it.

## Quick start

Install:

```bash
pip install thebleep
```

Add the normal alias to your shell configuration:

```bash
eval "$(thebleep --alias)"
```

Or avoid starting Python when your shell starts:

```bash
thebleep --alias-loader >> ~/.bashrc
```

Then make a mistake:

```bash
$ git brnch
git: 'brnch' is not a git command. See 'git --help'.

$ bleep
git branch [enter/↑/↓/ctrl+c/esc]
```

Want the old muscle memory?

```bash
eval "$(thebleep --alias fuck)"
```

## Safe by default

*The Bleep* asks before running a correction. In a non-interactive environment
(pipe, subprocess or CI), it does **not** silently apply the first suggestion;
use `--yes` when you explicitly want automatic application.

## Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Updating](#updating)
4. [How it works](#how-it-works)
5. [Creating your own rules](#creating-your-own-rules)
6. [Settings](#settings)
7. [Third-party packages with rules](#third-party-packages-with-rules)
8. [Experimental instant mode](#experimental-instant-mode)
9. [Performance](#performance)
10. [Developing](#developing)
11. [License](#license-mit)

## Requirements

- python (3.9+)
- pip
- python-dev

##### [Back to Contents](#contents)

## Installation

Install *The Bleep* by using `pip`:

```bash
pip install thebleep
```

On Ubuntu / Mint, the Python development packages are needed first:

```bash
sudo apt update
sudo apt install python3-dev python3-pip python3-setuptools
pip3 install thebleep --user
```

<a href='#manual-installation' name='manual-installation'>#</a>
It is recommended that you place this command in your `.bash_profile`,
`.bashrc`, `.zshrc` or other startup script:

```bash
eval $(thebleep --alias)
# You can use whatever you want as an alias, like for Mondays:
eval $(thebleep --alias BLEEP)
# Including the alias you may already be used to:
eval $(thebleep --alias fuck)
```

### Startup that costs nothing

The line above starts a Python interpreter every time you open a shell. To
avoid that, append the *loader* to your startup file once instead:

```bash
thebleep --alias-loader >> ~/.bashrc        # or ~/.zshrc, etc.
```

That writes a few lines of shell that define the alias the first time you use
it, and nothing before. It is static — it does not need regenerating when The
Bleep is upgraded, because all it does is call `thebleep --alias` on first use:

```bash
bleep() {
    eval "$(TB_SHELL=bash thebleep --alias bleep)";
    bleep "$@";
}
```

Use `eval $(thebleep --alias)` instead if you would rather pay at startup, and
for the experimental instant mode, which has to set your prompt up front.

[Shell-specific alias instructions (Bash, Zsh, Fish, Powershell, tcsh) are in *The Fuck*'s wiki](https://github.com/nvbn/thefuck/wiki/Shell-aliases)
and still apply, with `thefuck` replaced by `thebleep`.

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

```bash
pip3 install thebleep --upgrade
```

**Note: Alias functionality was changed in v1.34 of *The Fuck*, the upstream project**

## Uninstall

To remove *The Bleep*, reverse the installation process:
- erase or comment *thebleep* alias line from your Bash, Zsh, Fish, Powershell, tcsh, ... shell config
- use `pip` (or `pip3`) to uninstall the binaries

## How it works

*The Bleep* attempts to match the previous command with a rule. If a match is
found, a new command is created using the matched rule and executed. The
following rules are enabled by default:

* `adb_unknown_command` &ndash; fixes misspelled commands like `adb logcta`;
* `ag_literal` &ndash; adds `-Q` to `ag` when suggested;
* `aws_cli` &ndash; fixes misspelled commands like `aws dynamdb scan`;
* `az_cli` &ndash; fixes misspelled commands like `az providers`;
* `cargo` &ndash; runs `cargo build` instead of `cargo`;
* `cargo_no_command` &ndash; fixes wrong commands like `cargo buid`;
* `cat_dir` &ndash; replaces `cat` with `ls` when you try to `cat` a directory;
* `cd_correction` &ndash; spellchecks and corrects failed cd commands;
* `cd_cs` &ndash; changes `cs` to `cd`;
* `cd_mkdir` &ndash; creates directories before cd'ing into them;
* `cd_parent` &ndash; changes `cd..` to `cd ..`;
* `chmod_x` &ndash; adds execution bit;
* `choco_install` &ndash; appends common suffixes for chocolatey packages;
* `composer_not_command` &ndash; fixes composer command name;
* `conda_mistype` &ndash; fixes conda commands;
* `cp_create_destination` &ndash; creates a new directory when you attempt to `cp` or `mv` to a non-existent one
* `cp_omitting_directory` &ndash; adds `-a` when you `cp` directory;
* `cpp11` &ndash; adds missing `-std=c++11` to `g++` or `clang++`;
* `dirty_untar` &ndash; fixes `tar x` command that untarred in the current directory;
* `dirty_unzip` &ndash; fixes `unzip` command that unzipped in the current directory;
* `django_south_ghost` &ndash; adds `--delete-ghost-migrations` to failed because ghosts django south migration;
* `django_south_merge` &ndash; adds `--merge` to inconsistent django south migration;
* `docker_login` &ndash; executes a `docker login` and repeats the previous command;
* `docker_not_command` &ndash; fixes wrong docker commands like `docker tags`;
* `docker_image_being_used_by_container` &dash; removes the container that is using the image before removing the image;
* `dry` &ndash; fixes repetitions like `git git push`;
* `fab_command_not_found` &ndash; fixes misspelled fabric commands;
* `fix_alt_space` &ndash; replaces Alt+Space with Space character;
* `fix_file` &ndash; opens a file with an error in your `$EDITOR`;
* `gem_unknown_command` &ndash; fixes wrong `gem` commands;
* `git_add` &ndash; fixes *"pathspec 'foo' did not match any file(s) known to git."*;
* `git_add_force` &ndash; adds `--force` to `git add <pathspec>...` when paths are .gitignore'd;
* `git_bisect_usage` &ndash; fixes `git bisect strt`, `git bisect goood`, `git bisect rset`, etc. when bisecting;
* `git_branch_delete` &ndash; changes `git branch -d` to `git branch -D`;
* `git_branch_delete_checked_out` &ndash; changes `git branch -d` to `git checkout master && git branch -D` when trying to delete a checked out branch;
* `git_branch_exists` &ndash; offers `git branch -d foo`, `git branch -D foo` or `git checkout foo` when creating a branch that already exists;
* `git_branch_list` &ndash; catches `git branch list` in place of `git branch` and removes created branch;
* `git_branch_0flag` &ndash; fixes commands such as `git branch 0v` and `git branch 0r` removing the created branch;
* `git_checkout` &ndash; fixes branch name or creates new branch;
* `git_clone_git_clone` &ndash; replaces `git clone git clone ...` with `git clone ...`
* `git_clone_missing` &ndash; adds `git clone` to URLs that appear to link to a git repository.
* `git_commit_add` &ndash; offers `git commit -a ...` or `git commit -p ...` after previous commit if it failed because nothing was staged;
* `git_commit_amend` &ndash; offers `git commit --amend` after previous commit;
* `git_commit_reset` &ndash; offers `git reset HEAD~` after previous commit;
* `git_diff_no_index` &ndash; adds `--no-index` to previous `git diff` on untracked files;
* `git_diff_staged` &ndash; adds `--staged` to previous `git diff` with unexpected output;
* `git_fix_stash` &ndash; fixes `git stash` commands (misspelled subcommand and missing `save`);
* `git_flag_after_filename` &ndash; fixes `fatal: bad flag '...' after filename`
* `git_help_aliased` &ndash; fixes `git help <alias>` commands replacing <alias> with the aliased command;
* `git_hook_bypass` &ndash; adds `--no-verify` flag previous to `git am`, `git commit`, or `git push` command;
* `git_lfs_mistype` &ndash; fixes mistyped `git lfs <command>` commands;
* `git_main_master` &ndash; fixes incorrect branch name between `main` and `master`
* `git_merge` &ndash; adds remote to branch names;
* `git_merge_unrelated` &ndash; adds `--allow-unrelated-histories` when required
* `git_not_command` &ndash; fixes wrong git commands like `git brnch`;
* `git_pull` &ndash; sets upstream before executing previous `git pull`;
* `git_pull_clone` &ndash; clones instead of pulling when the repo does not exist;
* `git_pull_uncommitted_changes` &ndash; stashes changes before pulling and pops them afterwards;
* `git_push` &ndash; adds `--set-upstream origin $branch` to previous failed `git push`;
* `git_push_different_branch_names` &ndash; fixes pushes when local branch name does not match remote branch name;
* `git_push_pull` &ndash; runs `git pull` when `push` was rejected;
* `git_push_without_commits` &ndash; creates an initial commit if you forget and only `git add .`, when setting up a new project;
* `git_rebase_no_changes` &ndash; runs `git rebase --skip` instead of `git rebase --continue` when there are no changes;
* `git_remote_delete` &ndash; replaces `git remote delete remote_name` with `git remote remove remote_name`;
* `git_rm_local_modifications` &ndash; adds `-f` or `--cached` when you try to `rm` a locally modified file;
* `git_rm_recursive` &ndash; adds `-r` when you try to `rm` a directory;
* `git_rm_staged` &ndash;  adds `-f` or `--cached` when you try to `rm` a file with staged changes
* `git_rebase_merge_dir` &ndash; offers `git rebase (--continue | --abort | --skip)` or removing the `.git/rebase-merge` dir when a rebase is in progress;
* `git_remote_seturl_add` &ndash; runs `git remote add` when `git remote set_url` on nonexistent remote;
* `git_stash` &ndash; stashes your local modifications before rebasing or switching branch;
* `git_stash_pop` &ndash; adds your local modifications before popping stash, then resets;
* `git_tag_force` &ndash; adds `--force` to `git tag <tagname>` when the tag already exists;
* `git_two_dashes` &ndash; adds a missing dash to commands like `git commit -amend` or `git rebase -continue`;
* `go_run` &ndash; appends `.go` extension when compiling/running Go programs;
* `go_unknown_command` &ndash; fixes wrong `go` commands, for example `go bulid`;
* `gradle_no_task` &ndash; fixes not found or ambiguous `gradle` task;
* `gradle_wrapper` &ndash; replaces `gradle` with `./gradlew`;
* `grep_arguments_order` &ndash; fixes `grep` arguments order for situations like `grep -lir . test`;
* `grep_recursive` &ndash; adds `-r` when you try to `grep` directory;
* `grunt_task_not_found` &ndash; fixes misspelled `grunt` commands;
* `gulp_not_task` &ndash; fixes misspelled `gulp` tasks;
* `has_exists_script` &ndash; prepends `./` when script/binary exists;
* `heroku_multiple_apps` &ndash; adds `--app <app>` to `heroku` commands like `heroku pg`;
* `heroku_not_command` &ndash; fixes wrong `heroku` commands like `heroku log`;
* `history` &ndash; tries to replace command with the most similar command from history;
* `hostscli` &ndash; tries to fix `hostscli` usage;
* `ifconfig_device_not_found` &ndash; fixes wrong device names like `wlan0` to `wlp2s0`;
* `java` &ndash; removes `.java` extension when running Java programs;
* `javac` &ndash; appends missing `.java` when compiling Java files;
* `lein_not_task` &ndash; fixes wrong `lein` tasks like `lein rpl`;
* `long_form_help` &ndash; changes `-h` to `--help` when the short form version is not supported
* `ln_no_hard_link` &ndash; catches hard link creation on directories, suggest symbolic link;
* `ln_s_order` &ndash; fixes `ln -s` arguments order;
* `ls_all` &ndash; adds `-A` to `ls` when output is empty;
* `ls_lah` &ndash; adds `-lah` to `ls`;
* `man` &ndash; changes manual section;
* `man_no_space` &ndash; fixes man commands without spaces, for example `mandiff`;
* `mercurial` &ndash; fixes wrong `hg` commands;
* `missing_space_before_subcommand` &ndash; fixes command with missing space like `npminstall`;
* `mkdir_p` &ndash; adds `-p` when you try to create a directory without a parent;
* `mvn_no_command` &ndash; adds `clean package` to `mvn`;
* `mvn_unknown_lifecycle_phase` &ndash; fixes misspelled life cycle phases with `mvn`;
* `npm_missing_script` &ndash; fixes `npm` custom script name in `npm run-script <script>`;
* `npm_run_script` &ndash; adds missing `run-script` for custom `npm` scripts;
* `npm_wrong_command` &ndash; fixes wrong npm commands like `npm urgrade`;
* `no_command` &ndash; fixes wrong console commands, for example `vom/vim`;
* `no_such_file` &ndash; creates missing directories with `mv` and `cp` commands;
* `omnienv_no_such_command` &ndash; fixes wrong commands for `goenv`, `nodenv`, `pyenv` and `rbenv` (eg.: `pyenv isntall` or `goenv list`);
* `open` &ndash; either prepends `http://` to address passed to `open` or creates a new file or directory and passes it to `open`;
* `pip_install` &ndash; fixes permission issues with `pip install` commands by adding `--user` or prepending `sudo` if necessary;
* `pip_unknown_command` &ndash; fixes wrong `pip` commands, for example `pip instatl/pip install`;
* `php_s` &ndash; replaces `-s` by `-S` when trying to run a local php server;
* `port_already_in_use` &ndash; kills process that bound port;
* `prove_recursively` &ndash; adds `-r` when called with directory;
* `python_command` &ndash; prepends `python` when you try to run non-executable/without `./` python script;
* `python_execute` &ndash; appends missing `.py` when executing Python files;
* `python_module_error` &ndash; fixes ModuleNotFoundError by trying to `pip install` that module;
* `quotation_marks` &ndash; fixes uneven usage of `'` and `"` when containing args';
* `path_from_history` &ndash; replaces not found path with a similar absolute path from history;
* `rails_migrations_pending` &ndash; runs pending migrations;
* `react_native_command_unrecognized` &ndash; fixes unrecognized `react-native` commands;
* `remove_shell_prompt_literal` &ndash; removes leading shell prompt symbol `$`, common when copying commands from documentations;
* `remove_trailing_cedilla` &ndash; removes trailing cedillas `ç`, a common typo for European keyboard layouts;
* `rm_dir` &ndash; adds `-rf` when you try to remove a directory;
* `scm_correction` &ndash; corrects wrong scm like `hg log` to `git log`;
* `sed_unterminated_s` &ndash; adds missing '/' to `sed`'s `s` commands;
* `sl_ls` &ndash; changes `sl` to `ls`;
* `ssh_known_hosts` &ndash; removes host from `known_hosts` on warning;
* `sudo` &ndash; prepends `sudo` to the previous command if it failed because of permissions;
* `sudo_command_from_user_path` &ndash; runs commands from users `$PATH` with `sudo`;
* `switch_lang` &ndash; switches command from your local layout to en;
* `systemctl` &ndash; correctly orders parameters of confusing `systemctl`;
* `terraform_init.py` &ndash; runs `terraform init` before plan or apply;
* `terraform_no_command.py` &ndash; fixes unrecognized `terraform` commands;
* `test.py` &ndash; runs `pytest` instead of `test.py`;
* `touch` &ndash; creates missing directories before "touching";
* `tsuru_login` &ndash; runs `tsuru login` if not authenticated or session expired;
* `tsuru_not_command` &ndash; fixes wrong `tsuru` commands like `tsuru shell`;
* `tmux` &ndash; fixes `tmux` commands;
* `unknown_command` &ndash; fixes hadoop hdfs-style "unknown command", for example adds missing '-' to the command on `hdfs dfs ls`;
* `unsudo` &ndash; removes `sudo` from previous command if a process refuses to run on superuser privilege.
* `vagrant_up` &ndash; starts up the vagrant instance;
* `whois` &ndash; fixes `whois` command;
* `workon_doesnt_exists` &ndash; fixes `virtualenvwrapper` env name os suggests to create new.
* `wrong_hyphen_before_subcommand` &ndash; removes an improperly placed hyphen (`apt-install` -> `apt install`, `git-log` -> `git log`, etc.)
* `yarn_alias` &ndash; fixes aliased `yarn` commands like `yarn ls`;
* `yarn_command_not_found` &ndash; fixes misspelled `yarn` commands;
* `yarn_command_replaced` &ndash; fixes replaced `yarn` commands;
* `yarn_help` &ndash; makes it easier to open `yarn` documentation;

##### [Back to Contents](#contents)

The following rules are enabled by default on specific platforms only:

* `apt_get` &ndash; installs app from apt if it not installed (requires `python-commandnotfound` / `python3-commandnotfound`);
* `apt_get_search` &ndash; changes trying to search using `apt-get` with searching using `apt-cache`;
* `apt_invalid_operation` &ndash; fixes invalid `apt` and `apt-get` calls, like `apt-get isntall vim`;
* `apt_list_upgradable` &ndash; helps you run `apt list --upgradable` after `apt update`;
* `apt_upgrade` &ndash; helps you run `apt upgrade` after `apt list --upgradable`;
* `brew_cask_dependency` &ndash; installs cask dependencies;
* `brew_install` &ndash; fixes formula name for `brew install`;
* `brew_reinstall` &ndash; turns `brew install <formula>` into `brew reinstall <formula>`;
* `brew_link` &ndash; adds `--overwrite --dry-run` if linking fails;
* `brew_uninstall` &ndash; adds `--force` to `brew uninstall` if multiple versions were installed;
* `brew_unknown_command` &ndash; fixes wrong brew commands, for example `brew docto/brew doctor`;
* `brew_update_formula` &ndash; turns `brew update <formula>` into `brew upgrade <formula>`;
* `dnf_no_such_command` &ndash; fixes mistyped DNF commands;
* `nixos_cmd_not_found` &ndash; installs apps on NixOS;
* `pacman` &ndash; installs app with `pacman` if it is not installed (uses `yay`, `pikaur` or `yaourt` if available);
* `pacman_invalid_option` &ndash; replaces lowercase `pacman` options with uppercase.
* `pacman_not_found` &ndash; fixes package name with `pacman`, `yay`, `pikaur` or `yaourt`.
* `yum_invalid_operation` &ndash; fixes invalid `yum` calls, like `yum isntall vim`;

The following commands are bundled with *The Bleep*, but are not enabled by
default:

* `git_push_force` &ndash; adds `--force-with-lease` to a `git push` (may conflict with `git_push_pull`);
* `rm_root` &ndash; adds `--no-preserve-root` to `rm -rf /` command.

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

* `rules` &ndash; list of enabled rules, by default `thebleep.const.DEFAULT_RULES`;
* `exclude_rules` &ndash; list of disabled rules, by default `[]`;
* `require_confirmation` &ndash; requires confirmation before running new command, by default `True`;
  when there's no terminal attached (a pipe, a subprocess or CI) confirmation is impossible,
  so the suggestion is only printed and nothing is run &ndash; pass `--yes` to apply it;
* `wait_command` &ndash; the max amount of time in seconds for getting previous command output;
* `no_colors` &ndash; disable colored output;
* `priority` &ndash; dict with rules priorities, rule with lower `priority` will be matched first;
* `debug` &ndash; enables debug output, by default `False`;
* `history_limit` &ndash; the numeric value of how many history commands will be scanned, like `2000`;
* `alter_history` &ndash; push fixed command to history, by default `True`;
* `wait_slow_command` &ndash; max amount of time in seconds for getting previous command output if it in `slow_commands` list;
* `slow_commands` &ndash; list of slow commands;
* `num_close_matches` &ndash; the maximum number of close matches to suggest, by default `3`.
* `excluded_search_path_prefixes` &ndash; path prefixes to ignore when searching for commands, by default `[]`.

An example of `settings.py`:

```python
rules = ['sudo', 'no_command']
exclude_rules = ['git_push']
require_confirmation = True
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

* `THEBLEEP_RULES` &ndash; list of enabled rules, like `DEFAULT_RULES:rm_root` or `sudo:no_command`;
* `THEBLEEP_EXCLUDE_RULES` &ndash; list of disabled rules, like `git_pull:git_push`;
* `THEBLEEP_REQUIRE_CONFIRMATION` &ndash; require confirmation before running new command, `true/false`;
* `THEBLEEP_WAIT_COMMAND` &ndash; the max amount of time in seconds for getting previous command output;
* `THEBLEEP_NO_COLORS` &ndash; disable colored output, `true/false`;
* `THEBLEEP_PRIORITY` &ndash; priority of the rules, like `no_command=9999:apt_get=100`,
rule with lower `priority` will be matched first;
* `THEBLEEP_DEBUG` &ndash; enables debug output, `true/false`;
* `THEBLEEP_HISTORY_LIMIT` &ndash; how many history commands will be scanned, like `2000`;
* `THEBLEEP_ALTER_HISTORY` &ndash; push fixed command to history `true/false`;
* `THEBLEEP_WAIT_SLOW_COMMAND` &ndash; the max amount of time in seconds for getting previous command output if it in `slow_commands` list;
* `THEBLEEP_SLOW_COMMANDS` &ndash; list of slow commands, like `lein:gradle`;
* `THEBLEEP_NUM_CLOSE_MATCHES` &ndash; the maximum number of close matches to suggest, like `5`.
* `THEBLEEP_EXCLUDED_SEARCH_PATH_PREFIXES` &ndash; path prefixes to ignore when searching for commands, by default `[]`.

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

The default behavior of *The Bleep* requires time to re-run previous commands.
When in instant mode, *The Bleep* saves time by logging output with [script](https://en.wikipedia.org/wiki/Script_(Unix)),
then reading the log.

[![gif with instant mode][instant-mode-gif-link]][instant-mode-gif-link]

Currently, instant mode only supports Python 3 with bash or zsh. zsh's autocorrect function also needs to be disabled in order for thebleep to work properly.

To enable instant mode, add `--enable-experimental-instant-mode`
to the alias initialization in `.bashrc`, `.bash_profile` or `.zshrc`.

For example:

```bash
eval $(thebleep --alias --enable-experimental-instant-mode)
```

##### [Back to Contents](#contents)

## Performance

*The Bleep* is substantially faster than *The Fuck*, and the numbers are meant
to be checked rather than believed. Same machine, same Python, 30 runs each,
medians, measured with the harness in [`bench/`](bench/README.md). The
run behind this table is committed as `bench/results/final.json`:

| What you do | The Fuck 3.32 | The Bleep | |
| --- | ---: | ---: | ---: |
| Open a shell (`--alias` in your rc) | 205 ms | 38 ms | **5.4x** |
| Open a shell (pasted `--alias-loader`) | 205 ms | 0.3 ms | **no Python at all** |
| Correct a mistyped command | 240 ms | 57 ms | **4.2x** |
| Correct when nothing matches | 336 ms | 72 ms | **4.7x** |
| Correct after a command printed a megabyte | 3246 ms | 134 ms | **24.2x** |

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


[version-badge]:   https://img.shields.io/pypi/v/thebleep.svg?label=version
[version-link]:    https://pypi.python.org/pypi/thebleep/
[workflow-badge]:  https://github.com/stamparm/thebleep/workflows/Tests/badge.svg
[workflow-link]:   https://github.com/stamparm/thebleep/actions?query=workflow%3ATests
[license-badge]:   https://img.shields.io/badge/license-MIT-007EC7.svg
[examples-link]:   https://raw.githubusercontent.com/stamparm/thebleep/master/example.gif
[instant-mode-gif-link]:   https://raw.githubusercontent.com/stamparm/thebleep/master/example_instant_mode.gif

##### [Back to Contents](#contents)
