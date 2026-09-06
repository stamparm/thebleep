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
