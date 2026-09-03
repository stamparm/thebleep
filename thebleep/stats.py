# -*- encoding: utf-8 -*-

"""How often The Bleep has been used, and for what. Local, small, yours.

`thebleep --stats` answers the question people ask about a tool like this:
has it been worth it? The answer is a handful of counters kept in the
configuration directory -- corrections accepted, edited, run without asking,
times nothing was offered -- plus the slips fixed most often and the rules
that fixed them. Nothing about the commands themselves is kept except a
one-word slip and its fix, the same shape a learned correction has, and only
the hundred most frequent of each. It is never sent anywhere.

`--clear-cache` leaves it alone: it is a record, not a cache. `--stats reset`
starts it over.

"""

import os
import time

FORMAT = 1
FILE = 'stats.json'
MAX_FILE = 256 * 1024
TOP = 100
COUNTERS = ('accepted', 'edited', 'trusted', 'abstained')


def _path():
    from .learning import user_file

    return user_file(FILE)


def _empty():
    return {'format': FORMAT, 'since': time.time(), 'accepted': 0,
            'edited': 0, 'trusted': 0, 'abstained': 0, 'slips': {},
            'rules': {}}


def load():
    """The record as it stands; a fresh one when there is none or it is bad."""
    import json

    path = _path()
    if path is None:
        return _empty()
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        with os.fdopen(os.open(str(path), flags), 'rb') as handle:
            raw = handle.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            return _empty()
        value = json.loads(raw.decode('utf-8'))
    except Exception:
        return _empty()
    if not isinstance(value, dict) or value.get('format') != FORMAT:
        return _empty()
    record = _empty()
    for name in COUNTERS:
        if type(value.get(name)) is int and value[name] >= 0:
            record[name] = value[name]
    if isinstance(value.get('since'), (int, float)):
        record['since'] = value['since']
    for name in ('slips', 'rules'):
        table = value.get(name)
        if isinstance(table, dict):
            record[name] = {key: count for key, count in table.items()
                            if isinstance(key, str) and type(count) is int
                            and count > 0}
    return record


def _write(record):
    import json

    path = _path()
    if path is None:
        return False
    temp = None
    created = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.parent.joinpath('.thebleep-stats-{}.{}.tmp'.format(
            os.getpid(), time.time_ns()))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(str(temp), flags, 0o600)
        created = True
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(record, handle, ensure_ascii=False, sort_keys=True)
            handle.write('\n')
        os.replace(str(temp), str(path))
    except Exception:
        if temp is not None and created:
            try:
                os.unlink(str(temp))
            except OSError:
                pass
        return False
    return True


def _trim(table):
    """The `TOP` most frequent entries, ties broken by name for stability."""
    kept = sorted(table.items(), key=lambda item: (-item[1], item[0]))[:TOP]
    return dict(kept)


def _slip(before, after):
    """`gti -> git` when the two commands differ by one word, else None."""
    from . import learning

    spec = learning._spec(before, after)
    if spec is None:
        return None
    index = spec['index']
    return u'{} → {}'.format(spec['before_parts'][index],
                             spec['after_parts'][index])


def bump(counter, rule=None, before=None, after=None):
    """Count one event. Never raises; a record that cannot be kept is not."""
    try:
        record = load()
        if counter in COUNTERS:
            record[counter] += 1
        if rule:
            record['rules'][rule] = record['rules'].get(rule, 0) + 1
            record['rules'] = _trim(record['rules'])
        if before is not None and after is not None:
            slip = _slip(before, after)
            if slip:
                record['slips'][slip] = record['slips'].get(slip, 0) + 1
                record['slips'] = _trim(record['slips'])
        _write(record)
    except Exception:
        pass


def reset():
    return _write(_empty())


def _days(since):
    return max(int((time.time() - since) // 86400), 0)


def report(record=None):
    """The record as lines to print."""
    if record is None:
        record = load()
    total = record['accepted'] + record['edited']
    since = time.strftime('%Y-%m-%d', time.localtime(record['since']))
    lines = [u'Since {} ({} days): {} correction{}'.format(
        since, _days(record['since']), total, '' if total == 1 else 's')]
    if total or record['abstained']:
        lines.append(u'  accepted {}, edited {}, ran without asking {}'.format(
            record['accepted'], record['edited'], record['trusted']))
        lines.append(u'  nothing to offer {} time{}'.format(
            record['abstained'], '' if record['abstained'] == 1 else 's'))
    slips = sorted(record['slips'].items(), key=lambda item: (-item[1], item[0]))
    rules = sorted(record['rules'].items(), key=lambda item: (-item[1], item[0]))
    if slips:
        lines.append(u'Most fixed:')
        lines.extend(u'  {:>5}  {}'.format(count, slip)
                     for slip, count in slips[:10])
    if rules:
        lines.append(u'Rules that fixed most:')
        lines.extend(u'  {:>5}  {}'.format(count, rule)
                     for rule, count in rules[:10])
    if not total and not record['abstained']:
        lines.append(u'  nothing yet; it counts from the first correction')
    return lines


def print_report(mode=None):
    if mode == 'reset':
        print('Stats reset.' if reset() else 'Could not reset the stats.')
        return 0
    for line in report():
        print(line)
    return 0
