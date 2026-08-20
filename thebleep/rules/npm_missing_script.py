# -*- encoding: utf-8 -*-

"""`npm run buld` -> `npm run build`.

npm often prints the answer itself, and that is what to use:

    npm ERR! Missing script: "buld"
    npm ERR!
    npm ERR! Did you mean this?
    npm ERR!     npm run build # run the "build" package script

Asking `npm run-script` for the list instead -- which is what this did -- went
wrong twice over. It missed the lifecycle scripts, so `npm run strat` could not
reach `start`; and `replace_command` accepts a match as loose as 0.1, so
whatever was left in the list was offered anyway. On a real project that meant
`npm run strat` suggesting `npm run watch`, which is not a near miss: pressing
enter ran a script the user had not asked for.

So both are used: npm's suggestion and the project's own scripts go into one
pool and `replace_command` orders it by closeness. Neither source is trusted on
its own, because neither is reliably right -- npm answers `npm run dvelop` with
`watch-test` when the project has a `develop`, and offers nothing at all for the
lifecycle scripts. Closeness decides between them, which gets `build` from npm,
`start` from the list, and `develop` over npm's `watch-test`.

"""

import re
from thebleep.utils import for_app, replace_command
from thebleep.specific.npm import get_all_scripts, npm_available

enabled_by_default = npm_available

# npm used to write `missing script: build`; from npm 7 it is
# `Missing script: "build"`, and from npm 10 the `npm ERR!` prefix on the
# line became `npm error`.
MISSING_SCRIPT = re.compile(r'[Mm]issing script:\s*"?([^"\r\n]+?)"?\s*$',
                            re.MULTILINE)

# The name out of npm's own suggestion, whatever prefixes the line: `npm ERR!`
# on npm 7-9, `npm error` on npm 10, nothing at all when npm is not shouting.
SUGGESTED = re.compile(r'npm run(?:-script)?\s+(\S+)')


def _suggested(output):
    """What npm said it thought you meant, in the order it said it."""
    marker = output.find('Did you mean')
    if marker == -1:
        return []

    return SUGGESTED.findall(output[marker:])


@for_app('npm')
def match(command):
    return (any(part.startswith('ru') for part in command.script_parts)
            and MISSING_SCRIPT.search(command.output) is not None)


def get_new_command(command):
    misspelled_script = MISSING_SCRIPT.search(command.output).group(1)

    candidates = _suggested(command.output)
    candidates += [name for name in get_all_scripts()
                   if name not in candidates]

    return replace_command(command, misspelled_script, candidates)
