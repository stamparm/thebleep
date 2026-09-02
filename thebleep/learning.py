# -*- coding: utf-8 -*-

"""Small, local and explicit learned corrections.

Learning is deliberately narrower than a rule. A correction is eligible only
when it changes one shell word in a simple command. That gives a learned entry
an exact shape to match, instead of turning a user's one-off edit into a broad
string replacement with surprising consequences.
"""

import os

from .conf import settings


FORMAT = 1
LIMIT = 100
MAX_FILE = 256 * 1024
SCOPES = ('global', 'executable', 'repository')

# A repository can ship corrections of its own, for everyone who clones it:
# `.thebleep/corrections.json` at the root, a list of `before` and `after`
# pairs held to the same one-changed-word shape as a learned entry. Data, not
# code -- nothing in it is imported or run, and every word it produces is
# quoted for the shell like any learned word.
REPOSITORY_FILE = os.path.join('.thebleep', 'corrections.json')
REPOSITORY_FORMAT = 1
_CONTROL_WORDS = frozenset(('&&', '||', '|', ';', '(', ')'))


def _open_for_read(path):
    """Open learned state without following a symlink where supported."""
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    return os.fdopen(os.open(str(path), flags), 'rb')


def _path(name):
    user_dir = settings.user_dir
    if user_dir is None:
        # Management commands do not initialise all settings: they still need
        # to find the same config directory a correction would use.
        user_dir = settings._get_user_dir_path()
        settings.user_dir = user_dir
    path = user_dir.joinpath(name)
    return None if path.parts[:1] == ('~',) else path


def _read(name):
    import json

    path = _path(name)
    if path is None:
        return None
    try:
        with _open_for_read(path) as handle:
            raw = handle.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            return None
        value = json.loads(raw.decode('utf-8'))
    except Exception:
        return None
    return value


def _write(name, value):
    path = _path(name)
    if path is None:
        return False
    import json
    import time

    temp = None
    created = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.parent.joinpath('.thebleep-{}.{}.tmp'.format(
            os.getpid(), time.time_ns()))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(str(temp), flags, 0o600)
        created = True
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
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


def _valid_parts(parts):
    return (isinstance(parts, list) and parts
            and all(isinstance(part, str) for part in parts)
            and not _CONTROL_WORDS.intersection(parts))


def _valid_entry(entry):
    return (
        isinstance(entry, dict)
        and type(entry.get('id')) is int
        and entry['id'] > 0
        and isinstance(entry.get('before'), str)
        and isinstance(entry.get('after'), str)
        and entry['before'].strip()
        and entry['after'].strip()
        and entry['before'] != entry['after']
        and isinstance(entry.get('before_parts'), list)
        and isinstance(entry.get('after_parts'), list)
        and _valid_parts(entry['before_parts'])
        and _valid_parts(entry['after_parts'])
        and len(entry['before_parts']) == len(entry['after_parts'])
        and type(entry.get('index')) is int
        and 0 <= entry['index'] < len(entry['before_parts'])
        and entry['before_parts'][entry['index']]
        != entry['after_parts'][entry['index']]
        and isinstance(entry.get('executable'), str)
        and isinstance(entry.get('scope'), str)
        and entry['scope'] in SCOPES
        and (entry.get('root') is None or isinstance(entry['root'], str))
        and isinstance(entry.get('shell'), str)
        and isinstance(entry.get('created_at'), (int, float))
        and sum(old != new for old, new in zip(
            entry['before_parts'], entry['after_parts'])) == 1)


def _entries():
    value = _read('learned.json')
    if not isinstance(value, dict) or value.get('format') != FORMAT:
        return []
    return [entry for entry in value.get('entries', [])
            if _valid_entry(entry)][:LIMIT]


def load():
    """Return learned entries, newest first."""
    return _entries()


def _pending():
    value = _read('learning-pending.json')
    if not isinstance(value, dict) or value.get('format') != FORMAT:
        return None
    entry = value.get('entry')
    if not isinstance(entry, dict):
        return None
    checked = dict(entry, id=1, scope='global', root=None)
    return entry if _valid_entry(checked) else None


def _split(script):
    from .shells import shell

    try:
        parts = shell.split_command(script)
    except Exception:
        return None
    return parts if _valid_parts(parts) else None


def _spec(before, after):
    if not (isinstance(before, str) and isinstance(after, str)
            and before.strip() and after.strip() and before != after):
        return None
    before_parts = _split(before)
    after_parts = _split(after)
    if (before_parts is None or after_parts is None
            or len(before_parts) != len(after_parts)):
        return None
    changed = [index for index, (old, new) in enumerate(
        zip(before_parts, after_parts)) if old != new]
    if len(changed) != 1:
        return None

    from .utils import command_word_index

    command_index = command_word_index(before_parts)
    if command_index >= len(before_parts):
        return None
    return {'before': before,
            'after': after,
            'before_parts': before_parts,
            'after_parts': after_parts,
            'index': changed[0],
            'executable': before_parts[command_index],
            'command_index': command_index}


def remember_pending(before, after, cwd=None, shell_name=None):
    """Remember an eligible accepted correction for ``--learn-last``."""
    spec = _spec(before, after)
    if spec is None:
        return False
    import time

    spec['cwd'] = cwd if isinstance(cwd, str) else os.getcwd()
    spec['shell'] = shell_name if isinstance(shell_name, str) else ''
    spec['created_at'] = time.time()
    return _write('learning-pending.json', {'format': FORMAT, 'entry': spec})


def _repository_root(directory):
    if not isinstance(directory, str) or not directory:
        return None
    from .system import Path

    try:
        current = Path(directory).resolve()
    except (OSError, RuntimeError):
        return None
    while True:
        try:
            if current.joinpath('.git').exists():
                return str(current)
        except OSError:
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _under(directory, root):
    if not root:
        return False
    from .system import Path

    try:
        Path(directory).resolve().relative_to(Path(root).resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _new_id(entries):
    return max([entry['id'] for entry in entries] or [0]) + 1


def learn_last(scope='executable'):
    """Promote the pending accepted correction into a learned entry."""
    if scope not in SCOPES:
        raise ValueError('unknown learning scope')
    pending = _pending()
    if pending is None:
        return None
    root = _repository_root(pending.get('cwd')) if scope == 'repository' \
        else None
    if scope == 'repository' and root is None:
        return None

    entry = _store(dict(pending), scope, root)
    if entry is None:
        return None
    _write('learning-pending.json', {'format': FORMAT, 'entry': None})
    return entry


def _store(spec, scope, root):
    """Put `spec` at the front of the learned list; None when that failed."""
    entries = _entries()
    entry = dict(spec)
    entry.update({'id': _new_id(entries), 'scope': scope, 'root': root})
    entry.pop('cwd', None)
    entry.pop('command_index', None)
    entries = [old for old in entries
               if not all(old.get(key) == entry.get(key)
                          for key in ('before', 'after', 'scope', 'root',
                                      'shell'))]
    entries.insert(0, entry)
    if not _write('learned.json', {'format': FORMAT,
                                   'entries': entries[:LIMIT]}):
        return None
    return entry


def learn_pair(before, after, scope='executable', shell_name=None):
    """Learn `before` -> `after` directly, as `--learn-from-history` does."""
    if scope not in SCOPES:
        raise ValueError('unknown learning scope')
    spec = _spec(before, after)
    if spec is None:
        return None
    import time

    root = _repository_root(os.getcwd()) if scope == 'repository' else None
    if scope == 'repository' and root is None:
        return None
    spec['shell'] = shell_name if isinstance(shell_name, str) else ''
    spec['created_at'] = time.time()
    return _store(spec, scope, root)


# How far apart the two words of a fail-then-fix pair may be, and how short
# the word may be, before the pair stops looking like a typo and its fix.
# `git checkout main` followed by `git checkout dev` changes one word too,
# and is two commands rather than one mistake.
HISTORY_SCAN = 5000
SLIP_DISTANCE = 2
SLIP_LENGTH = 3


def _exists(program):
    from .utils import which

    return which(program) is not None


def _looks_like_a_slip(before_word, after_word):
    from . import matching

    if min(len(before_word), len(after_word)) < SLIP_LENGTH:
        return False
    if before_word.isdigit() or after_word.isdigit():
        return False
    if os.path.exists(before_word) and os.path.exists(after_word):
        # Two files that both exist are two files, not a misspelling.
        return False
    return matching.distance(before_word, after_word,
                             limit=SLIP_DISTANCE) <= SLIP_DISTANCE


def shell_history():
    from .shells import shell

    return shell.get_history()


def candidates_from_history(history=None):
    """Fail-then-fix pairs in the shell history, most repeated first.

    A line followed at once by the same line with one word changed, where the
    two words are a slip apart, is somebody making a mistake and fixing it;
    the same pair twice is a habit. Nothing is learned here -- these are
    proposals for `--learn-from-history` to show, each with how often it was
    seen. Pairs already learned, and lines that were The Bleep itself, are
    left out.

    :rtype: [dict] -- `before`, `after`, `spec`, `seen`

    """
    from .const import get_alias

    if history is None:
        history = shell_history()
    history = [line for line in history[-HISTORY_SCAN:]
               if line and not line.startswith(get_alias())]

    known = {(entry['before'], entry['after']) for entry in _entries()}
    found = {}
    for before, after in zip(history, history[1:]):
        if before == after or (before, after) in known:
            continue
        spec = _spec(before, after)
        if spec is None:
            continue
        index = spec['index']
        if not _looks_like_a_slip(spec['before_parts'][index],
                                  spec['after_parts'][index]):
            continue
        before_word = spec['before_parts'][index]
        after_word = spec['after_parts'][index]
        if index == spec['command_index'] and not (
                _exists(after_word) and not _exists(before_word)):
            # The changed word is the program: the fix has to be one that
            # exists, and the slip one that does not. `git status` followed
            # by `gti status` is the slip being made again, not a correction.
            continue
        key = (before_word, after_word, spec['executable'])
        if key in found:
            found[key]['seen'] += 1
        else:
            found[key] = {'before': before, 'after': after, 'spec': spec,
                          'seen': 1}
    # An argument changed one way and then back is two edits, not a slip and
    # its fix: whichever direction was seen less often is dropped.
    dropped = [key for key in found
               if (key[1], key[0], key[2]) in found
               and found[(key[1], key[0], key[2])]['seen'] >= found[key]['seen']]
    for key in dropped:
        del found[key]
    return sorted(found.values(), key=lambda item: -item['seen'])


def _current_shell_name():
    from .shells import shell

    return shell._shell_name()


def _read_repository_file(root):
    """The corrections a repository ships, or None when there are none."""
    import json

    path = os.path.join(root, REPOSITORY_FILE)
    try:
        if os.path.getsize(path) > MAX_FILE:
            return None
        with _open_for_read(path) as handle:
            raw = handle.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            return None
        value = json.loads(raw.decode('utf-8'))
    except Exception:
        return None
    if not isinstance(value, dict) or value.get('format') != REPOSITORY_FORMAT:
        return None
    corrections = value.get('corrections')
    return corrections if isinstance(corrections, list) else None


def repository_entries(cwd=None):
    """Entries from the repository's own file, shaped like learned ones.

    Each is a repository-scope entry rooted at the checkout, for any shell,
    and only the pairs that change exactly one word count -- the same bar a
    learned correction has to clear, for the same reason: an exact shape to
    match, not a string replacement.

    """
    root = _repository_root(cwd if cwd is not None else os.getcwd())
    if root is None:
        return []
    listed = _read_repository_file(root)
    if not listed:
        return []
    entries = []
    for number, item in enumerate(listed[:LIMIT], 1):
        if not isinstance(item, dict):
            continue
        spec = _spec(item.get('before'), item.get('after'))
        if spec is None:
            continue
        spec.pop('command_index', None)
        spec.update({'id': number, 'scope': 'repository', 'root': root,
                     'shell': '', 'created_at': 0, 'shipped': True})
        if _valid_entry(spec):
            entries.append(spec)
    return entries


def _matches(entry, parts, cwd, shell_name):
    if entry['shell'] and entry['shell'] != shell_name:
        return False
    if len(parts) != len(entry['before_parts']):
        return False
    if any(old != new for index, (old, new) in enumerate(
            zip(parts, entry['before_parts'])) if index != entry['index']):
        return False
    if parts[entry['index']] != entry['before_parts'][entry['index']]:
        return False
    if entry['scope'] == 'repository' and not _under(cwd, entry['root']):
        return False
    return True


def _render(entry, parts):
    from .shells import shell

    rendered = list(parts)
    rendered[entry['index']] = entry['after_parts'][entry['index']]
    return ' '.join(shell.quote(part) for part in rendered)


def corrections(command):
    """Yield learned corrections for a command in the current context."""
    from .types import CorrectedCommand, Rule

    parts = command.script_parts
    if not parts:
        return
    cwd = os.getcwd()
    entries = load() + repository_entries(cwd)
    if not entries:
        return
    shell_name = _current_shell_name()
    for entry in entries:
        if not _matches(entry, parts, cwd, shell_name):
            continue
        name = '{}_{}'.format(
            'shipped' if entry.get('shipped') else 'learned', entry['id'])
        rule = Rule(name,
                    lambda candidate, item=entry: _matches(
                        item, candidate.script_parts, os.getcwd(),
                        _current_shell_name()),
                    lambda candidate, item=entry: _render(
                        item, candidate.script_parts),
                    enabled_by_default=True, side_effect=None, priority=50,
                    requires_output=False)
        rule.learned = True
        rule.learning_scope = entry['scope']
        rule.learning_executable = entry['executable']
        rule.learning_shipped = bool(entry.get('shipped'))
        yield CorrectedCommand(_render(entry, parts), None, 50, rule=rule)


def forget(number):
    """Remove one learned entry by its current list number."""
    entries = _entries()
    if type(number) is not int or number < 1 or number > len(entries):
        return False
    entries.pop(number - 1)
    return _write('learned.json', {'format': FORMAT, 'entries': entries})


def print_entries(entries=None):
    """Print learned corrections without exposing implementation details."""
    if entries is None:
        entries = load()
    if not entries:
        print('No learned corrections.')
        return
    print('Learned corrections:')
    for index, entry in enumerate(entries, 1):
        print('{:>2}  {} -> {}  ({}, {})'.format(
            index, entry['before_parts'][entry['index']],
            entry['after_parts'][entry['index']], entry['scope'],
            entry['executable']))
