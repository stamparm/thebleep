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

    entries = _entries()
    entry = dict(pending)
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
    _write('learning-pending.json', {'format': FORMAT, 'entry': None})
    return entry


def _current_shell_name():
    from .shells import shell

    return shell._shell_name()


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

    entries = load()
    if not entries:
        return
    parts = command.script_parts
    if not parts:
        return
    cwd = os.getcwd()
    shell_name = _current_shell_name()
    for entry in entries:
        if not _matches(entry, parts, cwd, shell_name):
            continue
        rule = Rule('learned_{}'.format(entry['id']),
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
