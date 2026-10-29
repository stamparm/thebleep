# -*- encoding: utf-8 -*-

"""What return does under `--ambient`, for typing slips made by machine.

    python3 bench/typo_classes.py              # the table
    python3 bench/typo_classes.py --list wrong # ...and every wrong rewrite

Each seed is a real command; each class is one way fingers fail, applied at
every position: a space left out (`gitstatus`), a space typed one key early
(`gi tstatus`), a space after a dash (`ls - la`), a key dropped, doubled,
swapped with its neighbour or replaced by one beside it on QWERTY, and caps
lock or Shift. Nothing runs: the line is put to the same two questions the
bash binding asks, in the current directory and with this machine's `PATH`,
manual pages and completions -- so the numbers are this machine's.

`wrong` is the one to watch. A wrong rewrite happens before anything runs and
replaces what was typed; `none` only leaves the line to fail as it would
have. A seed whose program is not installed is skipped, and said so.

"""

import collections
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('TB_SHELL', 'bash')

from thebleep.conf import settings  # noqa: E402
from thebleep import ambient  # noqa: E402
from thebleep.serve import correct  # noqa: E402
from thebleep.utils import forget_memoized  # noqa: E402

SEEDS = ['git status', 'git commit -m x', 'git push', 'git pull', 'git log',
         'git diff', 'git branch', 'git checkout main', 'git stash',
         'git merge dev', 'git rebase main', 'git fetch', 'git clone url',
         'docker ps', 'docker images', 'docker run x', 'docker exec x sh',
         'docker build .', 'docker pull x', 'ls -la', 'grep -r foo .',
         'python3 -V', 'pip install x', 'pip list', 'npm install', 'npm test',
         'cargo build', 'make clean', 'df -h', 'du -sh .', 'ps aux',
         'cat f', 'head -n 3 f', 'tail -f log', 'systemctl status x',
         'journalctl -u x', 'apt install x', 'ssh host', 'curl -s url',
         'tar -xf a.tar', 'find . -name x', 'kill -9 1', 'chmod +x f',
         'mkdir -p a', 'less f', 'vim f', 'man ls', 'which ls',
         'sudo apt update', 'go build', 'node -v', 'kubectl get pods']

ROWS = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm']
NEAR = collections.defaultdict(set)
for r, row in enumerate(ROWS):
    for c, ch in enumerate(row):
        for dr in (-1, 0, 1):
            if 0 <= r + dr < 3:
                for dc in (-1, 0, 1):
                    if (dr, dc) != (0, 0) and 0 <= c + dc < len(ROWS[r + dr]):
                        NEAR[ch].add(ROWS[r + dr][c + dc])


def in_word(words, i, f):
    """Every mutation `f` makes of word i, as whole lines."""
    out = []
    for new in f(words[i]):
        if new != words[i] and new:
            out.append(' '.join(words[:i] + [new] + words[i + 1:]))
    return out


def omit(w):
    return [w[:k] + w[k + 1:] for k in range(len(w))]


def double(w):
    return [w[:k + 1] + w[k] + w[k + 1:] for k in range(len(w))]


def swap(w):
    return [w[:k] + w[k + 1] + w[k] + w[k + 2:]
            for k in range(len(w) - 1) if w[k] != w[k + 1]]


def near(w):
    return [w[:k] + n + w[k + 1:]
            for k in range(len(w)) for n in sorted(NEAR.get(w[k], ()))]


def mutations(seed):
    words = seed.split()
    m = collections.defaultdict(list)
    plain = [i for i, w in enumerate(words[:2]) if re.match(r'^[a-z][a-z0-9]+$', w)]
    for i in plain:
        m['omit'] += in_word(words, i, omit)
        m['double'] += in_word(words, i, double)
        m['swap'] += in_word(words, i, swap)
        m['adjacent'] += in_word(words, i, near)
    if len(words) > 1:
        m['fused'].append(words[0] + ' '.join(words[1:]))
        if len(words[0]) > 1:
            m['lagged'].append(' '.join([words[0][:-1], words[0][-1] + words[1]] + words[2:]))
    for i, w in enumerate(words):
        if re.match(r'^-[a-z]+$', w):
            m['stray'].append(' '.join(words[:i] + ['-', w[1:]] + words[i + 1:]))
    m['case'] += [seed.upper(), ' '.join([words[0].capitalize()] + words[1:]),
                  ' '.join([words[0].upper()] + words[1:])]
    if len(words) > 1 and words[1] in plain_words(words):
        m['case'].append(' '.join([words[0], words[1].upper()] + words[2:]))
    return m


def plain_words(words):
    return [w for w in words[1:2] if re.match(r'^[a-z][a-z0-9]+$', w)]


KIND = {}


def kind(word):
    if word not in KIND:
        KIND[word] = subprocess.run(['bash', '-c', 'type -t -- "$1"', '_', word],
                                    stdout=subprocess.PIPE, text=True).stdout.strip()
    return KIND[word]


def at_return(line):
    parts = line.split()
    first = parts[0]
    second = parts[1] if len(parts) > 1 else ''
    if not re.search(r'[/=$\'"`]', first) and not kind(first):
        forget_memoized()
        return correct(line)
    if second and re.match(r'[A-Za-z0-9]', first) and re.match(r'[A-Za-z0-9]', second) \
            and not re.search(r'[/=|;&<>(){}$\'"`\\]', line) and kind(first) == 'file':
        forget_memoized()
        return ambient.known_program_correction(line, os.getcwd())
    return None


def main(argv):
    settings.init()
    seeds = [s for s in SEEDS if kind(s.split()[0])]
    stats = collections.defaultdict(collections.Counter)
    wrong = collections.defaultdict(list)
    missed = collections.defaultdict(list)
    for seed in seeds:
        for cls, lines in mutations(seed).items():
            for line in dict.fromkeys(lines):
                if line == seed:
                    continue
                got = at_return(line)
                if got is None:
                    stats[cls]['none'] += 1
                    missed[cls].append(line)
                elif ' '.join(got.split()) == seed:
                    stats[cls]['right'] += 1
                else:
                    stats[cls]['wrong'] += 1
                    wrong[cls].append((line, got, seed))
    print('seeds %d (skipped, not installed: %s)'
          % (len(seeds), [s for s in SEEDS if s not in seeds]))
    tr = tw = tn = 0
    for cls, c in sorted(stats.items()):
        n = sum(c.values())
        tr += c['right']
        tw += c['wrong']
        tn += n
        print('%-9s %4d  right %5.1f%%  wrong %5.1f%%  none %5.1f%%' % (
            cls, n, 100.0 * c['right'] / n, 100.0 * c['wrong'] / n, 100.0 * c['none'] / n))
    print('%-9s %4d  right %5.1f%%  wrong %5.1f%%' % ('ALL', tn, 100.0 * tr / tn, 100.0 * tw / tn))

    if '--list' in argv:
        what = argv[argv.index('--list') + 1]
        for cls, rows in sorted((wrong if what == 'wrong' else missed).items()):
            for row in rows:
                print('%-9s %s' % (cls, row if isinstance(row, str)
                                   else '%-24s -> %-26s (meant %s)' % row))


if __name__ == '__main__':
    main(sys.argv[1:])
