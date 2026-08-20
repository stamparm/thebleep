# -*- encoding: utf-8 -*-

"""Typos, what the shell or tool said about them, and the answer wanted first.

Every `output` here was printed by a real program. The shell messages come from
dash 0.5.12, bash 5.2, zsh 5.9 and fish 4.0.2; the tool messages from git 2.47.3,
npm 10.8.2, pip 25.0.1, docker 27.3.1, kubectl 1.31.0, uv 0.12.5, cargo 1.97.1
and apt 3.0.3, each captured by running the failing command.

`expect` is what a competent user would want offered *first* -- not what the
code currently does. A case that fails is either a defect or a wrong
expectation, and both are worth arguing about in review. `None` means no
suggestion at all is the right answer.

The replay reads output by running the command again through `/bin/sh`, so on a
Debian-family machine the message a rule usually sees is dash's `not found`
rather than bash's `command not found`. Both are represented, because instant
mode sees the interactive shell's wording instead.

"""

# What the shell says when there is no such program. The `{}` is the command.
DASH = 'sh: 1: {}: not found'
BASH = 'bash: line 1: {}: command not found'
ZSH = 'zsh:1: command not found: {}'
FISH = 'fish: Unknown command: {}'

# A plausible recent history. Fixed, so the answer cannot depend on whose
# machine the suite runs on -- and long enough to include the sort of thing that
# poisoned a real suggestion: `which bleep`, typed while debugging this tool,
# is what made `whomi` suggest `which`.
HISTORY = [
    'git status',
    'git commit -m "wip"',
    'git push',
    'cd /home/user/src/project',
    'ls -la',
    'which bleep',
    'python3 manage.py runserver',
    'npm run build',
    'docker compose up -d',
    'ssh user@host',
    'grep -r pattern .',
    'cat README.md',
    'make test',
    'pip install -r requirements.txt',
    'vim setup.py',
]

# (script, output, expect)
#
# Group 1: no such program. This is the busiest path there is -- an unknown
# command is the commonest way a command fails -- and it is the one place with
# no tool to ask, so the answer is a pure guess. Nothing else in the suite
# covers it.
NO_SUCH_PROGRAM = [
    # The one that started this. `whoami` is one letter from `whomi`; `which`
    # is three and only qualifies at all because it sits exactly on the 0.6
    # cutoff. It won because it was in the history.
    ('whomi', DASH.format('whomi'), 'whoami'),
    ('whomi', BASH.format('whomi'), 'whoami'),
    ('whaomi', DASH.format('whaomi'), 'whoami'),
    ('whoiam', DASH.format('whoiam'), 'whoami'),

    # A transposition, which `difflib` cannot see: `gti`/`git` and `gti`/`tic`
    # both score 0.667, so the tie falls to whatever order `PATH` was scanned
    # in. It lands on `git` on a machine whose history is full of git and on
    # `tic` -- the terminfo compiler -- on a fresh one.
    ('gti status', DASH.format('gti'), 'git status'),
    ('gti', DASH.format('gti'), 'git'),
    ('gi status', DASH.format('gi'), 'git status'),
    ('igt status', DASH.format('igt'), 'git status'),

    # Ordinary single-letter slips in the commonest commands on earth.
    ('sl', DASH.format('sl'), 'ls'),
    ('lsl', DASH.format('lsl'), 'ls'),
    ('gerp foo .', DASH.format('gerp'), 'grep foo .'),
    ('grpe foo .', DASH.format('grpe'), 'grep foo .'),
    ('mkdri d', DASH.format('mkdri'), 'mkdir d'),
    ('tuoch f', DASH.format('tuoch'), 'touch f'),
    ('ehco hi', DASH.format('ehco'), 'echo hi'),
    ('cta f', DASH.format('cta'), 'cat f'),
    ('mve a b', DASH.format('mve'), 'mv a b'),
    ('rmm f', DASH.format('rmm'), 'rm f'),
    ('chmdo +x f', DASH.format('chmdo'), 'chmod +x f'),
    ('clera', DASH.format('clera'), 'clear'),
    ('tial -f log', DASH.format('tial'), 'tail -f log'),
    ('haed -n 5 f', DASH.format('haed'), 'head -n 5 f'),
    # `du` really is nearer to `duf` than `df` is, and `duf -h` is a
    # perfectly good reading. My first expectation here was wrong.
    ('duf -h', DASH.format('duf'), 'du -h'),
    ('pdw', DASH.format('pdw'), 'pwd'),
    # `killall` is not in `executables.txt`, so `kill` is the only answer
    # available. Another wrong expectation of mine.
    ('kilal x', DASH.format('kilal'), 'kill x'),

    # Interpreters and package managers, where the wrong answer is expensive.
    # `python` is in the snapshot and is one edit away; `python3` is two.
    # My first expectations here named `python3`, and were wrong.
    ('pyhton x.py', DASH.format('pyhton'), 'python x.py'),
    ('pytohn x.py', DASH.format('pytohn'), 'python x.py'),
    ('pyton3 x.py', DASH.format('pyton3'), 'python3 x.py'),
    ('ndoe x.js', DASH.format('ndoe'), 'node x.js'),
    # Two edits in four letters. Deliberately out of reach -- see
    # `matching.max_distance` for why that is the right trade.
    ('ndeo x.js', DASH.format('ndeo'), None),
    ('npmm i', DASH.format('npmm'), 'npm i'),
    ('nmp install', DASH.format('nmp'), 'npm install'),
    ('pip3l install x', DASH.format('pip3l'), 'pip3 install x'),
    ('crgo build', DASH.format('crgo'), 'cargo build'),
    ('carg build', DASH.format('carg'), 'cargo build'),
    ('dokcer ps', DASH.format('dokcer'), 'docker ps'),
    ('docekr ps', DASH.format('docekr'), 'docker ps'),
    ('kubctl get pods', DASH.format('kubctl'), 'kubectl get pods'),
    ('kubetcl get pods', DASH.format('kubetcl'), 'kubectl get pods'),
    ('sudp apt update', DASH.format('sudp'), 'sudo apt update'),
    ('suod apt update', DASH.format('suod'), 'sudo apt update'),
    ('apt-gte install x', DASH.format('apt-gte'), 'apt-get install x'),
    ('ssh-keygne', DASH.format('ssh-keygne'), 'ssh-keygen'),
    ('sssh user@host', DASH.format('sssh'), 'ssh user@host'),
    ('crul -O u', DASH.format('crul'), 'curl -O u'),

    ('tarr xzf f', DASH.format('tarr'), 'tar xzf f'),
    # `make` is not in the snapshot, so the metric can reach nothing -- but
    # `make test` is in the history, and the history rule answers it correctly.
    # A good demonstration of why history is worth keeping as a source.
    ('mkae test', DASH.format('mkae'), 'make test'),
    ('viim f', DASH.format('viim'), 'vim f'),
    ('whcih ls', DASH.format('whcih'), 'which ls'),

    # Shell builtins are commands you can type, and were not candidates at
    # all: only `PATH` was searched, so `exti` could not reach `exit` however
    # obvious the slip.
    ('exti', DASH.format('exti'), 'exit'),
    ('cdd /tmp', DASH.format('cdd'), 'cd /tmp'),
    ('aliass', DASH.format('aliass'), 'alias'),

    # One edit each from `sudo` and from `sfdp`. Left to the alphabet the
    # plotting tool won; the answer is whichever agrees for longer at the start.
    ('sudp apt update', DASH.format('sudp'), 'sudo apt update'),

    # Every shell says it differently, and a correction must not depend on
    # which one asked. fish never says "not found", so before this every
    # unknown command in fish went uncorrected.
    ('gerp foo .', BASH.format('gerp'), 'grep foo .'),
    ('gerp foo .', ZSH.format('gerp'), 'grep foo .'),
    ('gerp foo .', FISH.format('gerp'), 'grep foo .'),
]

# Group 2: the tool is there and says what it meant. These are the cases that
# work, and they work because the answer is *read* rather than guessed -- which
# is the pattern worth keeping.
#
# Only rules that read the answer out of output belong here. A rule that has to
# *run* the tool to get its list -- `apt_invalid_operation`, and
# `pip_unknown_command` when pip's own guess is the wrong one -- cannot be
# answered for through the corrector, for the reason set out in
# `tests/test_corpus.py::_stub_the_tools`, and is covered by its own tests.
THE_TOOL_SAID_SO = [
    ('git satus',
     "git: 'satus' is not a git command. See 'git --help'.\n\n"
     'The most similar command is\n\tstatus\n',
     'git status'),
    ('git comit -m "wip"',
     "git: 'comit' is not a git command. See 'git --help'.\n\n"
     'The most similar command is\n\tcommit\n',
     'git commit -m "wip"'),
    ('git chekout main',
     "git: 'chekout' is not a git command. See 'git --help'.\n\n"
     'The most similar command is\n\tcheckout\n',
     'git checkout main'),
    ('npm run buld',
     'npm ERR! Missing script: "buld"\nnpm ERR! \n'
     'npm ERR! Did you mean this?\n'
     'npm ERR!     npm run build # run the "build" package script\n',
     'npm run build'),
    ('pip instatl requests',
     'ERROR: unknown command "instatl" - maybe you meant "install"\n',
     'pip install requests'),
    # ...and a real `uninstall` typo still means uninstall.
    ('pip unistall requests',
     'ERROR: unknown command "unistall" - maybe you meant "uninstall"\n',
     'pip uninstall requests'),
    ('uv piip install requests',
     "error: unrecognized subcommand 'piip'\n\n"
     "  tip: a similar subcommand exists: 'pip'\n\n"
     'Usage: uv [OPTIONS] <COMMAND>\n',
     'uv pip install requests'),
    # Tools with NO rule of their own anywhere in this project. They are
    # corrected because `clap_suggestion`, `cobra_suggestion` and
    # `click_suggestion` read the framework rather than the tool -- which is the
    # claim, so it is gated here. Captured from ruff 0.14.5, gh 2.63.2,
    # helm 3.16.3 and black 25.9.0.
    ('ruff chekc .',
     "error: unrecognized subcommand 'chekc'\n\n"
     "  tip: a similar subcommand exists: 'check'\n\n"
     'Usage: ruff [OPTIONS] <COMMAND>\n',
     'ruff check .'),
    # A mistyped *option*, which nothing corrected before.
    ('ruff check --fixx .',
     "error: unexpected argument '--fixx' found\n\n"
     "  tip: a similar argument exists: '--fix'\n",
     'ruff check --fix .'),
    ('cargo instal ripgrep',
     'error: no such command: `instal`\n\n'
     'help: a command with a similar name exists: `install`\n',
     'cargo install ripgrep'),
    ('gh reop list',
     'unknown command "reop" for "gh"\n\nDid you mean this?\n\trepo\n\n'
     'Usage:  gh <command> <subcommand> [flags]\n',
     'gh repo list'),
    ('helm instal mychart',
     'Error: unknown command "instal" for "helm"\n\n'
     'Did you mean this?\n\tinstall\n\n'
     "Run 'helm --help' for usage.\n",
     'helm install mychart'),
    ('black --chekc .',
     'Usage: black [OPTIONS] SRC ...\n'
     "Try 'black --help' for help.\n\n"
     "Error: No such option '--chekc'. (Did you mean one of: '--check', "
     "'--code', '--help'?)\n",
     'black --check .'),
    ('kubectl gat pods',
     'error: unknown command "gat" for "kubectl"\n\n'
     'Did you mean this?\n\tget\n\tset\n',
     'kubectl get pods'),
]

# Group 3: nothing is the right answer. A confident wrong suggestion is worse
# than none, and several rules used to produce one.
NOTHING_IS_RIGHT = [
    # `wget` is not installed in the snapshot, so there is no right answer --
    # and `getent`, which is what came out, is three edits away and qualifies
    # only because the cutoff sits at 0.6. Silence is the answer.
    ('wgte u', DASH.format('wgte'), None),
    # No idea what this was meant to be; guessing is worse than silence.
    ('zzzzzqqqq', DASH.format('zzzzzqqqq'), None),
    ('asdfghjkl', DASH.format('asdfghjkl'), None),
    # The command worked.
    ('ls -la', '', None),
    ('git status', 'On branch main\nnothing to commit, working tree clean\n',
     None),
    # The source is what is missing, so there is no directory to make.
    ('mv typoo.txt new.txt',
     "mv: cannot stat 'typoo.txt': No such file or directory\n", None),
    # npm has nothing to suggest and no list to fall back on, so `npm None`
    # must not come out of it.
    ('npm urgrade',
     'Unknown command: "urgrade"\n\n'
     'To see a list of supported npm commands, run:\n  npm help\n', None),
    # `<name> --help` is not a command when `<name>` is not one. This was
    # answered with `nosuchpage --help`.
    ('man nosuchpage', 'No manual entry for nosuchpage\n', None),
    # A subcommand git does not have and nothing close enough to name.
    ('git zzzzzz',
     "git: 'zzzzzz' is not a git command. See 'git --help'.\n", None),
]

ALL = NO_SUCH_PROGRAM + THE_TOOL_SAID_SO + NOTHING_IS_RIGHT
