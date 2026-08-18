import os
import re
from functools import wraps
from . import cachefile, const
from .conf import settings
from .system import expanduser

# `pickle`, `shutil` and `difflib` are imported where they are used rather than
# here. Each one is a file the interpreter has to find and open before this
# module has done anything, and on Windows -- where a virus scanner sits in
# front of every open -- that is the most expensive part of a correction.
# `pickle` is only reached by a memoized call whose arguments cannot be hashed,
# `shutil.which` only by a rule that looks a program up, and `difflib` only by a
# rule that offers a spelling correction. None of the three is on the path a
# correction always takes.
#
# `difflib`'s function keeps its name here, bound on first use, because it is
# what the two functions below call and what a test replaces to see what they
# asked for.
difflib_get_close_matches = None


def _load_difflib():
    """Binds `difflib_get_close_matches`, once."""
    global difflib_get_close_matches
    if difflib_get_close_matches is None:
        from difflib import get_close_matches

        difflib_get_close_matches = get_close_matches


# Binary: nothing is ever written through this object -- it is only handed
# to Popen as a descriptor to throw output at -- and text mode would make
# it depend on the machine's default encoding for no reason.
DEVNULL = open(os.devnull, 'wb')


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
                import pickle
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


def _is_runnable(path):
    """Whether `path` names something this user could execute."""
    return (os.path.exists(path)
            and os.access(path, os.F_OK | os.X_OK)
            and not os.path.isdir(path))


@memoize
def which(program):
    """Returns `program` path or `None`.

    This was `shutil.which`, and importing `shutil` to ask it costs `bz2`,
    `lzma` and `zlib` -- the archive formats `make_archive` knows how to write
    -- before anything has been looked up. Several rules ask whether a program
    is installed while they are being imported, so a correction was paying for
    three compression libraries to find out whether Docker is on the machine.

    The lookup is the same one: the directories on `PATH`, plus the extensions
    `PATHEXT` lets a Windows user leave off, and of each candidate the question
    `shutil.which` asks -- is it there, is it not a directory, and may I run
    it. `tests/test_utils.py` holds it to agreeing with `shutil.which`.

    """
    # A name with a directory in it is not looked up on `PATH` at all; it is
    # either runnable where it points or it is nothing.
    if os.path.dirname(program):
        return program if _is_runnable(program) else None

    search = os.environ.get('PATH', os.defpath).split(os.pathsep)
    extensions = _executable_extensions()
    if extensions:
        # The current directory really is searched first on Windows, and a
        # rule that asks about a program in it would otherwise be told no.
        if os.curdir not in search:
            search.insert(0, os.curdir)
        if os.path.splitext(program)[1].lower() in extensions:
            names = [program]
        else:
            names = [program + extension for extension in extensions]
    else:
        names = [program]

    seen = set()
    for directory in search:
        normalised = os.path.normcase(directory)
        if not directory or normalised in seen:
            continue
        seen.add(normalised)
        for name in names:
            candidate = os.path.join(directory, name)
            if _is_runnable(candidate):
                return candidate


def load_subprocess(namespace):
    """Binds `Popen` and `PIPE` in a shell module's globals, and returns them.

    `subprocess` is not on the path a correction takes. Aliases arrive in the
    environment and a shell's version is only asked for when something prints
    diagnostics -- but importing it at the top of each shell module dragged
    `threading`, `signal`, `selectors`, `contextlib` and `locale` into every
    correction. On Windows, where finding and opening a module is the dearest
    thing an interpreter does, that was five modules for nothing.

    The two names stay module attributes rather than becoming local imports,
    because starting a process is what the shell tests replace and a name
    hidden inside a function body cannot be replaced. Each is bound separately
    and only when still unbound, so a test that has replaced `Popen` keeps its
    replacement and still gets a real `PIPE` to go with it.

    """
    if namespace.get('PIPE') is None:
        from subprocess import PIPE

        namespace['PIPE'] = PIPE
    if namespace.get('Popen') is None:
        from subprocess import Popen

        namespace['Popen'] = Popen
    return namespace['Popen'], namespace['PIPE']


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
    _load_difflib()
    possibilities = list(possibilities)
    try:
        return difflib_get_close_matches(word, possibilities, 1, cutoff)[0]
    except IndexError:
        if fallback_to_first:
            return possibilities[0]


# Windows resolves `ping` to `PING.EXE`, so a name that differs only in case
# is the same command to whoever typed it.
CASE_INSENSITIVE_NAMES = os.path.normcase('A') == os.path.normcase('a')


def get_close_matches(word, possibilities, n=None, cutoff=0.6):
    """Overrides `difflib.get_close_match` to control argument `n`."""
    _load_difflib()
    if n is None:
        n = settings.num_close_matches

    if not CASE_INSENSITIVE_NAMES:
        return difflib_get_close_matches(word, possibilities, n, cutoff)

    # Compare without case, but suggest each name the way it really is spelled.
    as_typed = {}
    for possibility in possibilities:
        as_typed.setdefault(possibility.lower(), possibility)

    return [as_typed[match]
            for match in difflib_get_close_matches(
                word.lower(), list(as_typed), n, cutoff)]


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


def _executable_extensions():
    """The extensions Windows lets you leave off when typing a command.

    Nobody types `pnpm.cmd`, so comparing a typo against the name with the
    extension still on it measures the wrong distance and finds nothing.

    """
    if os.name != 'nt':
        return ()

    # PATHEXT is semicolon-separated whatever `os.pathsep` says.
    return tuple(extension.lower()
                 for extension in os.environ.get('PATHEXT', '').split(';')
                 if extension.startswith('.'))


def _invocable_name(name, extensions):
    """`name` as it would be typed, with any implied extension dropped."""
    if extensions:
        stem, extension = os.path.splitext(name)
        if stem and extension.lower() in extensions:
            return stem

    return name


def _is_invocable(entry, extensions):
    """Whether typing this entry's name would run something.

    Every non-directory entry used to count, so a README in a directory on PATH
    was offered as a command -- and `get_close_matches` would offer a
    non-executable `realthinh` ahead of the `realthing` next to it, because it
    only compares spelling.

    On Windows the question is whether the extension is one the shell will run,
    which is what PATHEXT is. On POSIX it is the executable bit, asked as "could
    I run this", so that a file belonging to somebody else is not offered either.

    """
    if extensions:
        return os.path.splitext(entry.name)[1].lower() in extensions

    try:
        return os.access(entry.path, os.X_OK)
    except OSError:
        return False


def _scan_executables(paths, skip):
    """Every invocable entry in `paths`, cached until a directory changes.

    Scanning is a five-figure number of directory entries on a normal machine,
    which is far and away the slowest thing a correction used to do.

    """
    fingerprint = _path_fingerprint(paths) + (tuple(sorted(skip)),)
    cached = cachefile.load('executables', fingerprint,
                            EXECUTABLES_CACHE_MAX_AGE)
    if isinstance(cached, str):
        # One string split in C, rather than thirteen thousand strings
        # unmarshalled one at a time. A file name cannot contain a NUL, so it
        # is the one separator that is always safe.
        return cached.split('\0') if cached else []

    # A name that appears in several directories on $PATH is one command as
    # far as anyone typing it is concerned, and comparing it to a typo more
    # than once is work for nothing: nearly half the entries are repeats.
    found = []
    seen = set()
    extensions = _executable_extensions()
    for path in paths:
        try:
            entries = list(os.scandir(path))
        except OSError:
            continue
        for entry in entries:
            name = _invocable_name(entry.name, extensions)
            # Deduplicated before anything is asked of the filesystem: about
            # half the entries on a normal PATH are names seen in an earlier
            # directory, and each check is a syscall.
            if name in skip or name in seen:
                continue
            try:
                if entry.is_dir() or not _is_invocable(entry, extensions):
                    continue
            except OSError:
                continue
            seen.add(name)
            found.append(name)

    cachefile.save('executables', fingerprint, '\0'.join(found))
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
    """Helper for *_no_command rules.

    The replacement is quoted. Every caller's `matched` comes from somewhere
    outside: a tool's own output, `package.json`'s scripts, a Gruntfile's tasks,
    a repository's branches. Those are names, and a name is allowed to contain
    `;` or `$(...)` -- git accepts a branch called `feature;rm -rf ~`, npm
    accepts a script called the same -- while the result of this goes back to
    the shell to be evaluated. Quoting a plain word leaves it exactly as it was,
    so this costs the ordinary case nothing.

    """
    from thebleep.shells import shell

    new_cmds = get_close_matches(broken, matched, cutoff=0.1)
    return [replace_argument(command.script, broken,
                             shell.quote(new_cmd.strip()))
            for new_cmd in new_cmds]


# `FOO=bar command ...` runs `command` with `FOO` set for it; the assignments
# in front of it are not the command being run.
ENVIRONMENT_ASSIGNMENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')


def command_word_index(script_parts):
    """Where the command starts, past any environment assignments."""
    for index, part in enumerate(script_parts):
        if not ENVIRONMENT_ASSIGNMENT.match(part):
            return index

    return len(script_parts)


def is_app(command, *app_names, **kwargs):
    """Returns `True` if command is call to one of passed app names.

    Not memoized: it reads `script_parts`, which the command already keeps, so
    remembering the answer costs more than working it out again.

    """

    at_least = kwargs.pop('at_least', 0)
    if kwargs:
        raise TypeError("got an unexpected keyword argument '{}'".format(kwargs.keys()))

    parts = command.script_parts
    start = command_word_index(parts)

    if len(parts) - start > at_least:
        return os.path.basename(parts[start]) in app_names

    return False


def for_app(*app_names, **kwargs):
    """Specifies that matching script is for one of app names."""
    def _for_app(fn, command):
        if is_app(command, *app_names, **kwargs):
            return fn(command)
        else:
            return False

    return decorator(_for_app)


def _mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return 0


# Not `repr(fn).split('at')[0]`, which was the identity this used before: that
# is the repr up to the first literal "at", so `_get_operations` came out as
# `<function _get_oper` and any two functions in a module whose names agree up
# to their first "at" shared one cache entry and each got the other's answer.
UNSAFE_IN_A_FILE_NAME = re.compile(r'[^A-Za-z0-9_.-]')


def _cache_name(fn, args, kwargs):
    """What to file this function's answer under."""
    subject = u'{}.{}'.format(fn.__module__, fn.__qualname__)
    if args or kwargs:
        # A digest rather than `hash`, which Python randomises per process, so
        # that a call with the same arguments finds its answer next time. The
        # arguments are in the name and not only in the fingerprint so that two
        # different ones can be remembered at once.
        import hashlib

        detail = repr((args, tuple(sorted(kwargs.items())))).encode('utf-8')
        subject += '-' + hashlib.sha1(detail).hexdigest()[:12]
    return UNSAFE_IN_A_FILE_NAME.sub('_', subject)


def cache(*depends_on):
    """Caches a function's result on disk until one of `depends_on` changes.

    Only functions should be wrapped in `cache`, not methods.

    This used to be `shelve`, which meant `dbm` and `pickle` at import time, a
    database that dbm spreads over several files depending on which backend is
    available, an `atexit` handler to close it, and a "removing possibly
    out-dated cache" path for switching Python versions. `cachefile` already
    does the same job for the rule pack and the PATH listing: one file per
    subject, marshalled, written to a neighbour and moved into place, and a
    fingerprint saying what the answer was valid for.

    """
    def cache_decorator(fn):
        @memoize
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if cache.disabled:
                return fn(*args, **kwargs)

            paths = [expanduser(name).absolute().as_posix()
                     for name in depends_on]
            fingerprint = tuple((path, _mtime(path)) for path in paths)
            name = _cache_name(fn, args, kwargs)

            cached = cachefile.load(name, fingerprint)
            if cached is not None:
                return cached
            return cachefile.save(name, fingerprint, fn(*args, **kwargs))

        return wrapper

    return cache_decorator


cache.disabled = False


def get_installation_version():
    # `importlib.metadata` has been in the standard library since 3.8, so the
    # `pkg_resources` fallback that used to be here could never run — and
    # setuptools has since removed the thing it fell back to.
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version('thebleep')
    except PackageNotFoundError:
        # Running from a checkout that was never installed.
        return 'unknown'


# Re-exported: rules import it from here, and it lives in `const` so that
# printing an alias doesn't have to import this module.
get_alias = const.get_alias


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
