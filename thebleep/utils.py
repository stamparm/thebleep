import atexit
import os
import pickle
import re
import shutil
import sys
from difflib import get_close_matches as difflib_get_close_matches
from functools import wraps
from . import cachefile
from .logs import warn, exception
from .conf import settings
from .system import Path

DEVNULL = open(os.devnull, 'w')


def decorator(caller):
    """Turns a `caller(fn, *args, **kwargs)` function into a decorator.

    This used to come from the `decorator` package, which preserved the
    wrapped function's signature. Nothing here or in a rule inspects those
    signatures, and importing the package cost more than every rule's own
    import put together, so the four lines it was doing live here now.

    """
    def decorate(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return caller(fn, *args, **kwargs)

        return wrapper

    return decorate


def memoize(fn):
    """Caches previous calls to the function.

    The key is the arguments themselves when they can be hashed, and a pickle
    of them when they cannot. That distinction matters more than it looks:
    pickling a `Command` copies the whole output of the failed command, so a
    build that printed a megabyte used to be copied again for every memoized
    call made about it.

    """
    memo = {}

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not memoize.disabled:
            try:
                key = (args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
                key = pickle.dumps((args, kwargs))
            if key not in memo:
                memo[key] = fn(*args, **kwargs)
            value = memo[key]
        else:
            # Memoize is disabled, call the function
            value = fn(*args, **kwargs)

        return value

    return wrapper


memoize.disabled = False


@memoize
def which(program):
    """Returns `program` path or `None`."""
    return shutil.which(program)


def default_settings(params):
    """Adds default values to settings if it not presented.

    Usage:

        @default_settings({'apt': '/usr/bin/apt'})
        def match(command):
            print(settings.apt)

    """
    def _default_settings(fn, command):
        for k, w in params.items():
            settings.setdefault(k, w)
        return fn(command)
    return decorator(_default_settings)


def get_closest(word, possibilities, cutoff=0.6, fallback_to_first=True):
    """Returns closest match or just first from possibilities."""
    possibilities = list(possibilities)
    try:
        return difflib_get_close_matches(word, possibilities, 1, cutoff)[0]
    except IndexError:
        if fallback_to_first:
            return possibilities[0]


def get_close_matches(word, possibilities, n=None, cutoff=0.6):
    """Overrides `difflib.get_close_match` to control argument `n`."""
    if n is None:
        n = settings.num_close_matches
    return difflib_get_close_matches(word, possibilities, n, cutoff)


def include_path_in_search(path):
    return not any(path.startswith(x) for x in settings.excluded_search_path_prefixes)


def _search_path():
    return [path for path in os.environ.get('PATH', '').split(os.pathsep)
            if include_path_in_search(path)]


def _path_fingerprint(paths):
    """What makes a listing of `paths` valid: the directories and their mtimes.

    A directory's mtime changes when something is installed into it or removed
    from it, which is exactly when the listing stops being true.

    """
    fingerprint = []
    for path in paths:
        try:
            fingerprint.append((path, os.stat(path).st_mtime_ns))
        except OSError:
            fingerprint.append((path, 0))
    return tuple(fingerprint)


# How long a listing may be trusted even if no directory looks changed.
EXECUTABLES_CACHE_MAX_AGE = 600


def _scan_executables(paths, skip):
    """Every non-directory entry in `paths`, cached until a directory changes.

    Scanning is a five-figure number of directory entries on a normal machine,
    which is far and away the slowest thing a correction used to do.

    """
    fingerprint = _path_fingerprint(paths) + (tuple(sorted(skip)),)
    cached = cachefile.load('executables', fingerprint,
                            EXECUTABLES_CACHE_MAX_AGE)
    if cached is not None:
        return list(cached)

    found = []
    for path in paths:
        try:
            entries = list(os.scandir(path))
        except OSError:
            continue
        for entry in entries:
            if entry.name in skip:
                continue
            try:
                if entry.is_dir():
                    continue
            except OSError:
                continue
            found.append(entry.name)

    cachefile.save('executables', fingerprint, tuple(found))
    return found


@memoize
def get_all_executables():
    from thebleep.shells import shell

    tb_alias = get_alias()
    tb_entry_points = ('thebleep', 'bleep')

    bins = _scan_executables(_search_path(), tb_entry_points)
    aliases = [alias
               for alias in shell.get_aliases() if alias != tb_alias]

    return bins + aliases


def replace_argument(script, from_, to):
    """Replaces command line argument."""
    replaced_in_the_end = re.sub(u' {}$'.format(re.escape(from_)), u' {}'.format(to),
                                 script, count=1)
    if replaced_in_the_end != script:
        return replaced_in_the_end
    else:
        return script.replace(
            u' {} '.format(from_), u' {} '.format(to), 1)


@decorator
def eager(fn, *args, **kwargs):
    return list(fn(*args, **kwargs))


@eager
def get_all_matched_commands(stderr, separator='Did you mean'):
    if not isinstance(separator, list):
        separator = [separator]
    should_yield = False
    for line in stderr.split('\n'):
        for sep in separator:
            if sep in line:
                should_yield = True
                break
        else:
            if should_yield and line:
                yield line.strip()


def replace_command(command, broken, matched):
    """Helper for *_no_command rules."""
    new_cmds = get_close_matches(broken, matched, cutoff=0.1)
    return [replace_argument(command.script, broken, new_cmd.strip())
            for new_cmd in new_cmds]


def is_app(command, *app_names, **kwargs):
    """Returns `True` if command is call to one of passed app names.

    Not memoized: it reads `script_parts`, which the command already keeps, so
    remembering the answer costs more than working it out again.

    """

    at_least = kwargs.pop('at_least', 0)
    if kwargs:
        raise TypeError("got an unexpected keyword argument '{}'".format(kwargs.keys()))

    if len(command.script_parts) > at_least:
        return os.path.basename(command.script_parts[0]) in app_names

    return False


def for_app(*app_names, **kwargs):
    """Specifies that matching script is for one of app names."""
    def _for_app(fn, command):
        if is_app(command, *app_names, **kwargs):
            return fn(command)
        else:
            return False

    return decorator(_for_app)


class Cache(object):
    """Lazy read cache and save changes at exit."""

    def __init__(self):
        self._db = None

    def _init_db(self):
        try:
            self._setup_db()
        except Exception:
            exception("Unable to init cache", sys.exc_info())
            self._db = {}

    def _setup_db(self):
        # shelve costs dbm and pickle at import time, so it arrives only for
        # the rules that actually keep a cache.
        import dbm
        import shelve

        cache_dir = self._get_cache_dir()
        cache_path = Path(cache_dir).joinpath('thebleep').as_posix()

        try:
            self._db = shelve.open(cache_path)
        except dbm.error + (ImportError,):
            # Caused when switching between Python versions
            warn("Removing possibly out-dated cache")
            os.remove(cache_path)
            self._db = shelve.open(cache_path)

        atexit.register(self._db.close)

    def _get_cache_dir(self):
        default_xdg_cache_dir = os.path.expanduser("~/.cache")
        cache_dir = os.getenv("XDG_CACHE_HOME", default_xdg_cache_dir)

        # Ensure the cache_path exists, Python 2 does not have the exist_ok
        # parameter
        try:
            os.makedirs(cache_dir)
        except OSError:
            if not os.path.isdir(cache_dir):
                raise

        return cache_dir

    def _get_mtime(self, path):
        try:
            return str(os.path.getmtime(path))
        except OSError:
            return '0'

    def _get_key(self, fn, depends_on, args, kwargs):
        parts = (fn.__module__, repr(fn).split('at')[0],
                 depends_on, args, kwargs)
        return str(pickle.dumps(parts))

    def get_value(self, fn, depends_on, args, kwargs):
        if self._db is None:
            self._init_db()

        depends_on = [Path(name).expanduser().absolute().as_posix()
                      for name in depends_on]
        key = self._get_key(fn, depends_on, args, kwargs)
        etag = '.'.join(self._get_mtime(path) for path in depends_on)

        if self._db.get(key, {}).get('etag') == etag:
            return self._db[key]['value']
        else:
            value = fn(*args, **kwargs)
            self._db[key] = {'etag': etag, 'value': value}
            return value


_cache = Cache()


def cache(*depends_on):
    """Caches function result in temporary file.

    Cache will be expired when modification date of files from `depends_on`
    will be changed.

    Only functions should be wrapped in `cache`, not methods.

    """
    def cache_decorator(fn):
        @memoize
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if cache.disabled:
                return fn(*args, **kwargs)
            else:
                return _cache.get_value(fn, depends_on, args, kwargs)

        return wrapper

    return cache_decorator


cache.disabled = False


def get_installation_version():
    try:
        from importlib.metadata import version

        return version('thebleep')
    except ImportError:
        import pkg_resources

        return pkg_resources.require('thebleep')[0].version


def get_alias():
    return os.environ.get('TB_ALIAS', 'bleep')


@memoize
def get_valid_history_without_current(command):
    def _not_corrected(history, tb_alias):
        """Returns all lines from history except that comes before `bleep`."""
        previous = None
        for line in history:
            if previous is not None and line != tb_alias:
                yield previous
            previous = line
        if history:
            yield history[-1]

    from thebleep.shells import shell
    history = shell.get_history()
    tb_alias = get_alias()
    executables = set(get_all_executables())\
        .union(shell.get_builtin_commands())

    return [line for line in _not_corrected(history, tb_alias)
            if not line.startswith(tb_alias) and not line == command.script
            and line.split(' ')[0] in executables]


def format_raw_script(raw_script):
    """Creates single script from a list of script parts.

    :type raw_script: [basestring]
    :rtype: basestring

    """
    script = ' '.join(raw_script)

    return script.lstrip()
