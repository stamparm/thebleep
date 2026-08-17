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
from . import logs
from .conf import settings
from .system import Path

# Bumped whenever the layout or the metadata extraction changes, so an older
# pack is rebuilt instead of misread.
FORMAT = 2

# Decorators that tell us which app a rule is about. `sudo_support` is
# deliberately absent: it is transparent, and a `sudo`-prefixed command is
# resolved to the real app before dispatch.
APP_DECORATORS = {'git_support': ('git',)}


def _is_disabled():
    return os.environ.get('THEBLEEP_NO_RULE_PACK', '').lower() == 'true'


def _cache_path():
    """Where the pack lives. Keyed by interpreter, since code objects are."""
    cache_home = os.environ.get('XDG_CACHE_HOME') or '~/.cache'
    magic = MAGIC_NUMBER.hex()
    return Path(cache_home).expanduser().joinpath(
        'thebleep', 'rules-{}-{}.pack'.format(FORMAT, magic))


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
    entry = {'name': path.name[:-3],
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


def entries_for(paths):
    """Pack entries for `paths`, rebuilding whatever is missing or stale."""
    cached = _read_pack()
    entries = {}
    dirty = False
    for path in paths:
        key = str(path)
        entry = cached.get(key)
        try:
            stat = os.stat(key)
        except OSError:
            continue
        if not (entry and entry.get('mtime') == int(stat.st_mtime_ns)
                and entry.get('size') == int(stat.st_size)):
            try:
                entry = _build_entry(path)
            except Exception:
                logs.debug(u'Rule {} could not be packed'.format(path))
                continue
            dirty = True
        entries[key] = entry

    # The pack is rewritten when a rule changed, and also when the set of rules
    # changed, so removed and third-party rules don't linger in it.
    if dirty or set(entries) != set(cached):
        _write_pack(entries)
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
    `sudo_support` hands the unprefixed command to the rule.

    """
    parts = command.script_parts or command.script.split()
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


def get_rules_for(command, paths):
    """Rules that could match `command`, or None to fall back to a full load.

    Returns rules sorted by priority, exactly as a full load would, having
    executed only the rules that had a chance of matching.

    """
    if _is_disabled():
        return None

    from .types import Rule

    try:
        entries = entries_for(paths)
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
    for path, entry in candidates:
        name = entry['name']
        with logs.debug_time(u'Importing rule: {};'.format(name)):
            try:
                module = load_module(name, path, entry['code'])
            except Exception:
                logs.exception(u'Rule {} failed to load'.format(name),
                               sys.exc_info())
                continue
        try:
            rule = Rule.from_module(name, module)
        except Exception:
            logs.exception(u'Rule {} is not a rule'.format(name),
                           sys.exc_info())
            continue
        if rule.is_enabled:
            rules.append(rule)

    return sorted(rules, key=lambda rule: rule.priority)


def clear():
    """Removes the pack. Returns the path it tried to remove."""
    path = _cache_path()
    try:
        os.unlink(str(path))
    except OSError:
        pass
    return path
