"""A cache of compiled rules, with enough metadata to skip loading most of them.

Loading rules used to dominate every invocation: each of the ~170 rule modules
was read, parsed, compiled and executed before a single one was consulted, and
nothing was cached to disk. Two observations make that avoidable.

The first is that compiling is the expensive part and its result is cacheable:
a marshalled code object loads about twenty times faster than the source it came
from compiles.

The second is that most rules already declare what they are about. A rule
decorated with ``@for_app('git', ...)`` cannot match ``brew install``, and that
declaration can be read from the syntax tree without executing anything. So the
pack stores, per rule, the compiled code plus the little that dispatch needs to
decide whether the rule is worth executing at all.

Everything here is an optimisation and nothing here is authoritative: a missing,
stale, corrupt or unwritable pack only costs time, never correctness, and the
caller falls back to loading rules the slow way.
"""

import ast
import marshal
import os
import sys
import types as pytypes
from importlib.util import MAGIC_NUMBER
from . import cachefile, logs
from .conf import settings

# Bumped whenever the layout or the metadata extraction changes, so an older
# pack is rebuilt instead of misread.
FORMAT = 3

# Decorators that tell us which app a rule is about. `sudo_support` is
# deliberately absent: it is transparent, and a `sudo`-prefixed command is
# resolved to the real app before dispatch.
APP_DECORATORS = {'git_support': ('git',)}

# Every decorator we understand well enough to draw a conclusion past.
#
# A decorator we do not know could be doing anything -- somebody's own could
# ignore the wrapped function and answer for itself -- and then neither the
# `for_app` underneath it nor the body of `match` says what the rule will
# actually match. So a rule with one is left to run for every command, which
# costs a millisecond and cannot be wrong. Every bundled rule uses only these
# three, so nothing bundled pays for it.
KNOWN_DECORATORS = frozenset({'for_app', 'git_support', 'sudo_support'})


def _is_disabled():
    return os.environ.get('THEBLEEP_NO_RULE_PACK', '').lower() == 'true'


def _cache_path():
    """Where the pack lives. Keyed by interpreter, since code objects are.

    The directory comes from `cachefile`, which is the one place that decides
    where anything cached goes -- and the one place that has to cope with there
    being no home directory to put it in.

    """
    magic = MAGIC_NUMBER.hex()
    return cachefile.directory().joinpath(
        'rules-{}-{}.pack'.format(FORMAT, magic))


# Metadata extraction ------------------------------------------------------


def _literal(node):
    """Returns (True, value) for a literal node, (False, None) otherwise."""
    try:
        return True, ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False, None


def _decorator_name(node):
    """`@for_app(...)`, `@mod.for_app(...)` and `@git_support` -> the name."""
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _apps_from_decorators(decorators):
    """Which apps a `match` function is restricted to, or None if unknown."""
    apps = set()
    for decorator in decorators:
        name = _decorator_name(decorator)
        if name in APP_DECORATORS:
            apps.update(APP_DECORATORS[name])
        elif name == 'for_app':
            if not isinstance(decorator, ast.Call):
                return None
            for arg in decorator.args:
                if isinstance(arg, ast.Starred):
                    return None
                ok, value = _literal(arg)
                if not ok or not isinstance(value, str):
                    return None
                apps.add(value)
    return tuple(sorted(apps)) or None


def _output_reference(node):
    """Recognises `command.output` and `command.output.lower()`.

    Returns (matched, case_insensitive).

    """
    case_insensitive = False
    if isinstance(node, ast.Call) and not node.args and not node.keywords \
            and isinstance(node.func, ast.Attribute):
        if node.func.attr != 'lower':
            return False, False
        case_insensitive = True
        node = node.func.value
    if isinstance(node, ast.Attribute) \
            and node.attr in ('output', 'stdout', 'stderr') \
            and isinstance(node.value, ast.Name) and node.value.id == 'command':
        return True, case_insensitive
    return False, False


def _output_term(node):
    """`'needle' in command.output` -> the needle that must be in the output."""
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return None
    if not isinstance(node.ops[0], ast.In):
        return None
    ok, needle = _literal(node.left)
    if not ok or not isinstance(needle, str) or not needle:
        return None
    matched, case_insensitive = _output_reference(node.comparators[0])
    if not matched:
        return None
    return (needle.lower(), True) if case_insensitive else (needle, False)


def _output_clauses(node):
    """Output substrings that `match` cannot return true without.

    The result is a conjunction of alternatives — every clause must be
    satisfied by at least one of its needles — which is exactly how `and` and
    `or` compose. A term we don't understand contributes no clause, so an
    unrecognised rule keeps being loaded for every command.

    """
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        clauses = []
        for operand in node.values:
            clauses.extend(_output_clauses(operand))
        return clauses

    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        # An `or` is only a requirement when every branch is one, otherwise the
        # unknown branch could be what makes the rule match.
        alternatives = []
        for operand in node.values:
            branch = _output_clauses(operand)
            if len(branch) != 1:
                return []
            alternatives.extend(branch[0])
        return [tuple(alternatives)]

    term = _output_term(node)
    return [(term,)] if term else []


def _match_body_expression(node):
    """The single expression a `match` function returns, if that's all it does.

    Rules that branch, assign or loop are left alone: proving what they need
    would take a real analyser, and being wrong here means a missed correction.

    """
    body = [statement for statement in node.body
            if not (isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str))]
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return None
    return body[0].value


def _extract_metadata(source, path):
    """Reads what dispatch needs from a rule's syntax tree.

    Anything that isn't a plain literal is reported as unknown, which makes the
    rule a candidate for every command — slower, never wrong.

    """
    meta = {'apps': None, 'enabled': None, 'priority': None,
            'requires_output': None, 'output': ()}
    tree = ast.parse(source, filename=path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == 'enabled_by_default':
                    ok, value = _literal(node.value)
                    meta['enabled'] = value if ok and isinstance(value, bool) \
                        else None
                elif target.id == 'priority':
                    ok, value = _literal(node.value)
                    meta['priority'] = value if ok and isinstance(value, int) \
                        else None
                elif target.id == 'requires_output':
                    ok, value = _literal(node.value)
                    meta['requires_output'] = value \
                        if ok and isinstance(value, bool) else None
        elif isinstance(node, ast.FunctionDef) and node.name == 'match':
            if any(_decorator_name(decorator) not in KNOWN_DECORATORS
                   for decorator in node.decorator_list):
                continue
            meta['apps'] = _apps_from_decorators(node.decorator_list)
            expression = _match_body_expression(node)
            if expression is not None:
                meta['output'] = tuple(_output_clauses(expression))
    return meta


def _build_entry(path):
    """Compiles one rule file and extracts its metadata."""
    with open(str(path), 'rb') as handle:
        source = handle.read()
    stat = os.stat(str(path))
    entry = {'name': os.path.basename(str(path))[:-3],
             'mtime': int(stat.st_mtime_ns),
             'size': int(stat.st_size),
             'code': marshal.dumps(compile(source, str(path), 'exec'))}
    try:
        entry.update(_extract_metadata(source, str(path)))
    except SyntaxError:
        # A rule that doesn't parse won't execute either, but that is the
        # loader's problem to report, not ours.
        entry.update({'apps': None, 'enabled': None, 'priority': None,
                      'requires_output': None})
    return entry


# The pack itself ----------------------------------------------------------


def _read_pack():
    path = _cache_path()
    try:
        with path.open('rb') as handle:
            pack = marshal.load(handle)
    except Exception:
        return {}
    if not isinstance(pack, dict) or pack.get('magic') != MAGIC_NUMBER \
            or pack.get('format') != FORMAT:
        return {}
    entries = pack.get('entries')
    return entries if isinstance(entries, dict) else {}


def _write_pack(entries):
    """Writes the pack where the next run can find it, or gives up quietly."""
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written to a neighbouring temporary file and moved into place, so a
        # second shell reading the pack never sees a half-written one.
        temp = path.parent.joinpath('{}.{}.tmp'.format(path.name, os.getpid()))
        with temp.open('wb') as handle:
            marshal.dump({'format': FORMAT, 'magic': MAGIC_NUMBER,
                          'entries': entries}, handle)
        os.replace(str(temp), str(path))
    except Exception:
        logs.debug(u'Rule pack not written to {}'.format(path))
        try:
            os.unlink(str(temp))
        except Exception:
            pass


def _is_well_formed(entry, key):
    """Whether an entry from the pack has the shape dispatch expects.

    Dispatch believes what the pack tells it, so a value of the wrong type there
    is not a slow correction but a wrong one: `apps` holding a string rather
    than a tuple of them makes `apps.intersection` compare characters, and a
    `name` that does not belong to the file decides enablement by somebody
    else's settings. Anything that does not look right is treated as missing and
    built again from the source.

    A value that is well formed but untrue -- `apps` naming a command no rule is
    about -- reads exactly like a valid entry for a rule that does not apply,
    and nothing here can tell the difference. What stands behind that is the
    file's size and modification time, recorded and checked below.

    """
    if not isinstance(entry, dict):
        return False
    if entry.get('name') != os.path.basename(key)[:-3]:
        return False
    if not isinstance(entry.get('code'), bytes):
        return False
    if not isinstance(entry.get('mtime'), int) \
            or not isinstance(entry.get('size'), int):
        return False
    apps = entry.get('apps')
    if apps is not None and not (isinstance(apps, tuple)
                                 and all(isinstance(app, str)
                                         for app in apps)):
        return False
    for field, kind in (('enabled', bool), ('priority', int),
                        ('requires_output', bool)):
        value = entry.get(field)
        if value is not None and not isinstance(value, kind):
            return False
    clauses = entry.get('output', ())
    if not isinstance(clauses, tuple):
        return False
    for clause in clauses:
        if not isinstance(clause, tuple) or not clause:
            return False
        for term in clause:
            if not (isinstance(term, tuple) and len(term) == 2
                    and isinstance(term[0], str)
                    and isinstance(term[1], bool)):
                return False
    return True


def entries_for(paths, stats=None):
    """Pack entries for `paths`, rebuilding whatever is missing or stale.

    `stats` maps a path to the `(mtime_ns, size)` a caller has already been told
    -- by the directory listing it used to find these files in the first place.
    Anything missing from it is asked for here, so a caller that has nothing to
    offer loses nothing.

    """
    cached = _read_pack()
    stats = stats or {}
    entries = {}
    dirty = False
    for path in paths:
        key = str(path)
        entry = cached.get(key)
        if entry is not None and not _is_well_formed(entry, key):
            entry = None
        known = stats.get(key)
        if known is None:
            try:
                stat = os.stat(key)
            except OSError:
                continue
            known = (int(stat.st_mtime_ns), int(stat.st_size))
        mtime, size = known
        if not (entry and entry.get('mtime') == mtime
                and entry.get('size') == size):
            try:
                entry = _build_entry(path)
            except Exception:
                logs.debug(u'Rule {} could not be packed'.format(path))
                continue
            dirty = True
        entries[key] = entry

    # Rules belonging to another installation are kept rather than evicted:
    # a checkout and an installed copy share this file, and dropping each
    # other's entries would have them rebuilding the pack in turn, forever.
    # Entries whose file has gone are the ones that get pruned.
    keep = {key: entry for key, entry in cached.items()
            if key not in entries and os.path.exists(key)}
    if dirty or set(keep) != set(cached) - set(entries):
        _write_pack(dict(keep, **entries))
    return entries


def load_module(name, path, code_bytes):
    """Executes a cached code object as a module, like an import would."""
    module = pytypes.ModuleType(name)
    module.__file__ = path
    exec(marshal.loads(code_bytes), module.__dict__)
    return module


# Dispatch -----------------------------------------------------------------


def command_apps(command):
    """The app names a command could plausibly be about.

    The first word, and the second as well when the first is `sudo`, because
    `sudo_support` hands the unprefixed command to the rule. Environment
    assignments in front of the command are skipped, exactly as `is_app` skips
    them, so that dispatch and the rules agree on what the command is.

    """
    from .utils import command_word_index

    parts = command.script_parts or command.script.split()
    parts = parts[command_word_index(parts):]
    if not parts:
        return frozenset()
    apps = {os.path.basename(parts[0])}
    if apps == {'sudo'} and len(parts) > 1:
        apps.add(os.path.basename(parts[1]))
    return frozenset(apps)


def _is_enabled(name, entry):
    """`Rule.is_enabled`, decided from metadata instead of a loaded module."""
    if name in settings.rules:
        return True
    from .const import ALL_ENABLED
    enabled_by_default = entry['enabled']
    if enabled_by_default is None:
        enabled_by_default = True
    return enabled_by_default and ALL_ENABLED in settings.rules


def _output_satisfied(clauses, output, lowered):
    """Whether the command's output can satisfy what the rule requires of it."""
    for clause in clauses:
        for needle, case_insensitive in clause:
            haystack = lowered if case_insensitive else output
            if needle in haystack:
                break
        else:
            return False
    return True


def candidate_entries(entries, command):
    """Entries worth executing for this command, in stable path order."""
    apps = command_apps(command)
    output = command.output
    lowered = output.lower() if output else ''
    out = []
    for key in sorted(entries):
        entry = entries[key]
        name = entry['name']
        if name == '__init__' or name in settings.exclude_rules:
            continue
        if not _is_enabled(name, entry):
            continue
        rule_apps = entry['apps']
        if rule_apps is not None and not apps.intersection(rule_apps):
            continue
        # Output requirements only rule a rule out when there is an output to
        # check them against; `requires_output = False` rules run either way.
        if output and entry.get('output') \
                and not _output_satisfied(entry['output'], output, lowered):
            continue
        out.append((key, entry))
    return out


def get_rules_for(command, paths, stats=None):
    """Rules that could match `command`, or None to fall back to a full load.

    Returns rules sorted by priority, exactly as a full load would, having
    executed only the rules that had a chance of matching.

    """
    if _is_disabled():
        return None

    from .types import Rule

    try:
        entries = entries_for(paths, stats)
    except Exception:
        logs.exception(u'Rule pack unusable, loading rules directly',
                       sys.exc_info())
        return None
    if not entries:
        return None

    candidates = candidate_entries(entries, command)
    logs.debug(u'Rule pack: {} of {} rules are candidates for {}'.format(
        len(candidates), len(entries), sorted(command_apps(command))))

    rules = []
    damaged = False
    for path, entry in candidates:
        name = entry['name']
        with logs.debug_time(u'Importing rule: {};'.format(name)):
            try:
                rule = Rule.from_module(
                    name, load_module(name, path, entry['code']))
            except Exception:
                # The cached code is an optimisation and nothing more. A rule
                # that will not load out of it is loaded from its source
                # instead: a damaged pack may cost time, and must never make a
                # correction disappear or change which one is offered first.
                logs.debug(u'Rule {} not usable from the pack'.format(name))
                rule = Rule.from_path(path)
                damaged = rule is not None
        if rule is not None and rule.is_enabled:
            rules.append(rule)

    if damaged:
        # The source loaded, so it is the pack that is wrong rather than the
        # rule. Thrown away so the next run builds a good one.
        _forget()

    return sorted(rules, key=lambda rule: rule.priority)


def _forget():
    """Removes this interpreter's pack, quietly."""
    try:
        os.unlink(str(_cache_path()))
    except OSError:
        pass


def clear():
    """Removes every rule pack, including ones left by other interpreters.

    Returns how many were removed.

    """
    removed = 0
    try:
        for path in _cache_path().parent.glob('rules-*.pack'):
            try:
                os.unlink(str(path))
                removed += 1
            except OSError:
                pass
    except Exception:
        pass
    return removed
