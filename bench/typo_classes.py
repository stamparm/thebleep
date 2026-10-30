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

Two more classes: `keep`, lines that are right as typed with the arguments
people really give them (`ssh adm`, `make ssl`, `npm ci`) -- any rewrite is
wrong -- and `alias`, a program's first letter fused to its subcommand
(`gcomit`). The keyboard is a physical one: rows staggered, neighbours within
1.3 key widths, the same geometry `thebleep.matching` measures with.

After a failure is measured in containers, one per family, where the typos
run for real with no network and the engine reads what they printed:

    python3 bench/typo_classes.py --emit debian \\
        | docker run --rm -i --network none -v "$PWD:/src:ro" <image> \\
            python3 /src/bench/typo_after.py /work

`<image>` is the family's base with the tool, Python, `psutil` and `pyte`
installed and `PYTHONPATH=/src`; `typo_after.py` prints one JSON row per typo.

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

FAMILIES = {
    'debian': ['git status', 'git commit -m x', 'git push', 'git log',
               'git diff', 'git branch', 'git checkout main', 'git stash',
               'git merge dev', 'git rebase main', 'git fetch',
               'apt install vim', 'apt-get update', 'apt search vim',
               'pip install requests', 'pip list', 'python3 -V', 'ls -la',
               'grep -r foo .', 'tar -xf a.tar', 'make clean', 'cat f',
               'head -n 3 f', 'du -sh .', 'df -h', 'chmod +x f', 'mkdir -p a',
               'find . -name x', 'ps aux', 'ssh host', 'less f', 'man ls',
               'which ls', 'kill -9 1', 'tail -f log', 'curl -s url'],
    'node': ['npm install', 'npm test', 'npm run build', 'npm ls',
             'yarn add x', 'yarn install', 'pnpm install', 'node -v'],
    'rust': ['cargo build', 'cargo test', 'cargo run', 'cargo check',
             'cargo clippy', 'rustup update'],
    'golang': ['go build', 'go test ./...', 'go mod tidy', 'go run .',
               'go vet ./...'],
    'fedora': ['dnf install vim', 'dnf search vim', 'dnf upgrade',
               'rpm -qa'],
    'opensuse': ['zypper install vim', 'zypper search vim',
                 'zypper refresh'],
    'alpine': ['apk add vim', 'apk search vim', 'apk update'],
    'arch': ['pacman -S vim', 'pacman -Ss vim', 'pacman -Syu'],
    'docker': ['docker ps', 'docker images', 'docker run x',
               'docker exec x sh', 'docker build .', 'docker pull x',
               'docker logs x', 'docker compose up'],
    'local': ['kubectl get pods', 'systemctl status x', 'journalctl -u x',
              'node -v', 'go build', 'gh pr list', 'helm list', 'uv sync',
              'snap list', 'flatpak list', 'openssl version', 'ip addr',
              'sudo apt update', 'vim f', 'tmux ls', 'gpg --list-keys'],
}
SEEDS = sorted({seed for seeds in FAMILIES.values() for seed in seeds})

# Lines that are right as typed, with the arguments real people give them:
# hostnames, targets, files, branches, scripts. Any rewrite is wrong.
KEEP = ['ssh adm', 'ssh web1', 'ssh db', 'ssh arm', 'ssh pi', 'ssh nas',
        'ssh dev', 'ssh addr', 'ssh agnet', 'ping gw', 'make all',
        'make test', 'make install', 'make ssl', 'make dist', 'make docs',
        'cat notes', 'cat stauts', 'git checkout dev', 'git checkout fix',
        'git log main', 'git rm f', 'git mv a b', 'git show', 'git tag',
        'npm run dev', 'npm ci', 'npm ls', 'npm i', 'npm init',
        'docker cp a b', 'docker rm x', 'docker rmi x', 'docker top x',
        'docker logs web', 'docker run nginx', 'apt show git',
        'apt list', 'apt remove x', 'apt purge x', 'apt autoremove',
        'pip show x', 'pip freeze', 'pip check', 'cargo run', 'cargo add x',
        'go run .', 'go get x', 'python3 app.py', 'node app', 'man ssh',
        'which python', 'cd src', 'ls src', 'vim notes', 'less log',
        'ip a', 'ip r', 'ip link', 'kubectl logs api', 'kubectl cp a b',
        'systemctl restart nginx', 'systemctl stop x', 'journalctl -f',
        'gpg --list-keys', 'openssl rand 8', 'flatpak run x', 'snap run x',
        'tmux a', 'tmux new', 'gh repo view', 'helm ls', 'uv run x',
        'git st', 'git co main', 'git ci', 'git br', 'npm t', 'npm rb',
        'docker ps -a', 'kill %1', 'tar tf a.tar', 'grep -rn x .']

# A physical QWERTY: each row starts further right than the one above it,
# and two keys are neighbours when their centres are within 1.3 key widths.
ROWS = ((0.50, 'qwertyuiop'), (0.75, 'asdfghjkl'), (1.25, 'zxcvbnm'))
PLACE = {ch: (offset + col, row) for row, (offset, keys) in enumerate(ROWS)
         for col, ch in enumerate(keys)}
NEAR = collections.defaultdict(set)
for a, (ax, ay) in PLACE.items():
    for b, (bx, by) in PLACE.items():
        if a != b and ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 <= 1.3:
            NEAR[a].add(b)


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
    if len(words) > 1 and plain_words(words):
        m['alias'] += [words[0][0] + words[1]] + [
            words[0][0] + new for new in omit(words[1]) if len(new) > 2]
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


def emit(family):
    import json
    for seed in FAMILIES[family]:
        for cls, lines in sorted(mutations(seed).items()):
            if cls in ('alias',):
                continue
            for line in dict.fromkeys(lines):
                if line != seed:
                    print(json.dumps([cls, line, seed]))


def main(argv):
    if argv[:1] == ['--emit']:
        return emit(argv[1])
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
    for line in KEEP:
        if not kind(line.split()[0]):
            continue
        got = at_return(line)
        if got is None:
            stats['keep']['right'] += 1
        else:
            stats['keep']['wrong'] += 1
            wrong['keep'].append((line, got, line))
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
