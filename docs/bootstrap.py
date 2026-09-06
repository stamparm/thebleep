# -*- coding: utf-8 -*-

"""The machine the playground corrects against, fixed so a stranger can trust it.

This module runs unchanged in CPython and in a browser under Pyodide, and both
callers matter. `assets/make_playground.py` imports it to precompute the answers
the page draws at first paint; the page imports it again once the WebAssembly
interpreter is up, so that a typo a visitor types themselves goes through
exactly the code that produced the precomputed ones. One implementation, so the
two cannot drift into disagreeing about the same command.

Nothing here needs psutil or pyte. The engine reaches for both lazily and only
down paths a browser never takes -- with one exception, which is why `TB_SHELL`
is set below: `thebleep.shells` walks the process tree with psutil at *import*
time when the environment does not name a shell, and a browser tab has no
process tree to walk.

The PATH and the history are fixed for the same reason `tests/corpus` fixes
them: an answer that depends on whose machine it ran against is not an answer
you can show to a stranger. A browser has neither, so without this the whole
no-such-program family -- the commonest way a command fails, and the only one
with no tool to ask -- would answer nothing at all.

Order matters. `install()` has to run before the first correction, because
`thebleep.rulepack` loads each rule from its source file and a rule sees
whatever `thebleep.utils` holds at the moment it is loaded. Patch first and
every rule reads the fixed machine; patch afterwards and the rules already
loaded are still asking the real one.

"""

import os

# What the corpus answers for `npm run-script`. Captured from npm 10.8.2.
NPM_SCRIPTS = ['build', 'test', 'start', 'watch']

# The third leg of the fixed machine, after the PATH and the history.
#
# Seventeen rules answer by looking at what is actually on disk: `cat /tm/ad`
# becomes `cat /tmp/ad` because `path_correction` walks the path and finds
# `tmp` sitting beside what was typed. A browser tab starts with none of that,
# so every one of those rules silently declined and the page looked like a
# spell-checker for program names -- which undersells the tool badly.
#
# `install_filesystem` is called by the page and *not* by the generator. The
# generator runs on somebody's real machine, where `/etc` is not ours to write
# to; the browser's is a private sandbox that starts empty and dies with the
# tab.
PROJECT = '/home/user/src/project'

DIRECTORIES = [
    '/etc', '/tmp', '/var/log', '/usr/bin', '/usr/local/bin',
    '/home/user', '/home/user/Documents', '/home/user/Downloads',
    PROJECT, PROJECT + '/src', PROJECT + '/tests', PROJECT + '/.git',
]

FILES = {
    '/etc/passwd': 'root:x:0:0:root:/root:/bin/bash\n',
    '/etc/hosts': '127.0.0.1\tlocalhost\n',
    '/etc/hostname': 'demo\n',
    '/etc/fstab': '',
    '/tmp/notes.txt': 'a scratch file\n',
    '/var/log/syslog': '',
    '/home/user/.bashrc': '',
    PROJECT + '/README.md': '# project\n',
    PROJECT + '/Makefile': 'build:\n\techo building\n\ntest:\n\techo testing\n',
    PROJECT + '/package.json':
        '{"name": "project", "scripts": {"build": "tsc", "test": "jest",'
        ' "start": "node .", "watch": "tsc -w"}}\n',
    PROJECT + '/src/index.js': '',
    PROJECT + '/tests/test_index.js': '',
}

# How many candidates the page has room to show. The first is the one that
# would be run, and the only one the corpus asserts.
LIMIT = 3

_installed = False


def install(executables, history):
    """Point the engine at a fixed PATH and a fixed history.

    `executables` is the PATH snapshot from `tests/corpus/executables.txt` and
    `history` the fixed list from `tests/corpus/cases.py`. The page ships both
    inside `cases.json`, so the browser never has to reach back into the repo
    for them.
    """
    global _installed

    # Before importing anything from the package: `thebleep.shells` decides at
    # import time, and psutil is what it falls back on. Set rather than
    # defaulted, so the answer cannot depend on the shell the generator
    # happened to be run from.
    os.environ['TB_SHELL'] = 'bash'

    from thebleep import const, utils, vocabulary
    from thebleep.conf import settings
    from thebleep.specific import npm

    names = list(executables)
    present = set(names)
    remembered = list(history)

    utils.get_all_executables = lambda: list(names)
    utils.get_valid_history_without_current = lambda command: list(remembered)
    utils.which = lambda name: ('/usr/bin/' + name
                                if os.path.basename(name) in present else None)

    # `vocabulary` reads the machine's own man pages and fish completions, and
    # which tools a machine has documented is a fact about that machine. A
    # browser has none, and none are worth freezing into the page.
    vocabulary.facts = lambda *args, **kwargs: {
        'subcommands': [], 'nested': {}, 'options': {}}

    npm.get_scripts = lambda *args, **kwargs: list(NPM_SCRIPTS)
    npm.get_all_scripts = lambda *args, **kwargs: list(NPM_SCRIPTS)

    settings.init()
    settings.num_close_matches = 3
    # npm's rules are gated on npm being installed -- which no browser is --
    # so they answer nothing at all unless named here ahead of the gate.
    settings.rules = [const.ALL_ENABLED, 'npm_missing_script',
                      'npm_wrong_command']

    # A memoised answer taken from the real machine would outlive every patch
    # above, and the first correction is what would fill the cache.
    utils.memoize.disabled = True

    _installed = True


# Slips against the tree above, and what the real program says about each.
#
# The wordings were captured by running the failing command against a tree of
# this shape -- coreutils 9.4 for `cat`, `ls` and `rm`, dash 0.5.12 for `cd` --
# and only the path in them is substituted, which is the same thing
# `tests/corpus/cases.py` does with its `sh: 1: {}: not found`.
#
# Every one of these needs the output: with an empty box the rules that read
# the filesystem all decline, because a path that is missing now may simply
# have been created since. So these are the page's own worked examples rather
# than something a visitor would reach by typing a command alone.
SCENARIOS = [
    ('cat /tm/notes.txt',
     'cat: /tm/notes.txt: No such file or directory'),
    ('cat /ec/passwd',
     'cat: /ec/passwd: No such file or directory'),
    ('cat /home/user/.bashrx',
     'cat: /home/user/.bashrx: No such file or directory'),
    ('cd /hom/user',
     "sh: 1: cd: can't cd to /hom/user"),
    ('cd /home/user/Documnets',
     "sh: 1: cd: can't cd to /home/user/Documnets"),
    ('cd tets',
     "sh: 1: cd: can't cd to tets"),
    ('cat ' + PROJECT,
     'cat: ' + PROJECT + ': Is a directory'),
    ('rm ' + PROJECT + '/src',
     "rm: cannot remove '" + PROJECT + "/src': Is a directory"),
]


def scenarios():
    """The worked examples above, answered here and now.

    Not precomputed like the corpus ones: they need the tree that only exists
    inside the sandbox, and answering them where they are shown is also the
    plainest evidence the page is running an engine rather than reciting a
    table.
    """
    return [dict(script=script, output=output, expect=None,
                 **answer(script, output))
            for script, output in SCENARIOS]


def install_filesystem():
    """Lay out the demo tree and stand in it. Browser only -- see FILES.

    Deliberately not called from `install()`. Somebody will one day import this
    module on a real machine to reproduce an answer, and the difference between
    the two functions is the difference between reading their `/etc` and
    writing to it.
    """
    for path in DIRECTORIES:
        try:
            os.makedirs(path)
        except OSError:
            pass                      # already there: nothing to do

    for path, contents in FILES.items():
        with open(path, 'w') as handle:
            handle.write(contents)

    # `wrong_directory` and the project rules answer relative to where you are
    # standing, and a visitor is standing in the project.
    os.chdir(PROJECT)


def answer(script, output=None):
    """Correct one command, trimmed to what the page draws.

    `suggest` also returns the parsed command model and a prose explanation
    that repeats `evidence_details` in another shape. Neither is worth the
    bytes in a file a visitor downloads before anything appears on screen.
    """
    if not _installed:
        raise RuntimeError('install() must run before the first correction')

    from thebleep import api

    result = api.suggest(script, output or None)
    return {'decision': result['decision'],
            'suggestions': [_trim(item)
                            for item in result['suggestions'][:LIMIT]]}


def _trim(suggestion):
    return {'command': suggestion['command'],
            'edits': suggestion['edits'],
            'rule': suggestion['rule'],
            'confidence': suggestion['confidence'],
            'risk': suggestion['risk'],
            'risk_factors': suggestion['risk_factors'],
            'side_effect': suggestion['side_effect'],
            'evidence': suggestion['evidence_details']}
