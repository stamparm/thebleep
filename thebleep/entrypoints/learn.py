# -*- encoding: utf-8 -*-

"""`--learn-from-history`: the corrections you have been making by hand.

`--learn-last` learns one correction, the one just accepted. The history
already holds hundreds of them: every time a line was followed by the same
line with one word fixed, that was a correction made by hand, and the same
pair twice is a habit worth keeping. This reads those pairs out, shows them
with how often each was seen, and learns the ones you say yes to. Nothing is
learned without the yes -- or `all`, which is the yes said once.

"""

import sys

from .. import learning, logs
from ..conf import settings


def _shown(candidate):
    spec = candidate['spec']
    index = spec['index']
    return u'{} -> {}  ({}, seen {})'.format(
        spec['before_parts'][index], spec['after_parts'][index],
        spec['executable'], candidate['seen'])


def learn_from_history(args):
    settings.init(args)
    mode = args.learn_from_history or 'ask'
    candidates = learning.candidates_from_history()
    if not candidates:
        print('No typo-then-fix pairs found in the history.')
        return 0

    from ..shells import shell

    shell_name = shell._shell_name()

    if mode == 'list':
        for number, candidate in enumerate(candidates, 1):
            print(u'{:>2}  {}'.format(number, _shown(candidate)))
        print('Run `thebleep --learn-from-history` to choose, or '
              '`--learn-from-history all` to keep them all.')
        return 0

    from ..ui import is_interactive

    if mode == 'ask' and not is_interactive():
        for number, candidate in enumerate(candidates, 1):
            print(u'{:>2}  {}'.format(number, _shown(candidate)))
        logs.failed('No terminal to ask on; rerun with `--learn-from-history '
                    'all` to keep them all')
        return 1

    from ..system import get_key

    learned = 0
    for candidate in candidates:
        if mode == 'ask':
            sys.stderr.write(u'{}  keep it? [y/n/q] '.format(_shown(candidate)))
            sys.stderr.flush()
            while True:
                key = get_key()
                if key in ('y', 'Y', 'n', 'N', 'q', 'Q', '\x03'):
                    break
            sys.stderr.write(u'{}\n'.format(key if key != '\x03' else 'q'))
            if key in ('q', 'Q', '\x03'):
                break
            if key in ('n', 'N'):
                continue
        entry = learning.learn_pair(candidate['before'], candidate['after'],
                                    'executable', shell_name)
        if entry is not None:
            learned += 1
    print('Learned {} correction{}.'.format(learned, '' if learned == 1 else 's'))
    return 0
