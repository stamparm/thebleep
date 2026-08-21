# -*- encoding: utf-8 -*-

"""`thebleep --doctor`: what is installed, what is configured, what is wrong.

Most of what gets reported as a mysterious bug is one of a dozen things, and
every one of them is a fact about the machine rather than about the code: the
alias is in a file this shell does not read, `thebleep` on `PATH` is an older
copy in a different environment, the settings file has a typo in it so every
setting in it was dropped, the shell was guessed wrong, `~/.config/thefuck` was
never copied over. Each is a round trip to find out and a second one to fix.

Two rules govern what this prints.

**It is safe to paste.** A diagnostic ends up in an issue, so it says that a
setting is set and not what it is set to, that an alias is defined and not what
it expands to, which rules exist and not what is in them. Nothing is read out
of the environment except the handful of names The Bleep itself defines, and
those are reported as set or unset. Paths have the home directory folded back to
`~`, so a username is not carried along either.

**It does not change anything.** Nothing here creates the config directory,
writes a settings file or builds the rule pack -- a report that has to alter the
machine before it can describe it is describing a different machine.

"""

import os
import sys
from .. import const, logs

# Everything reported: a heading, the finding, and how much it matters.
OK = 'ok'
WARN = 'warn'
NOTE = 'note'


class Report(object):
    """The findings, in the order they were made."""

    def __init__(self):
        self.lines = []

    def add(self, label, value, status=OK, advice=None):
        self.lines.append((label, value, status, advice))

    @property
    def problems(self):
        return [line for line in self.lines if line[2] == WARN]


def _home():
    try:
        home = os.path.expanduser('~')
    except Exception:                                        # pragma: no cover
        return None
    return home if home and home != '~' else None


def tidy(path):
    """A path with the home directory folded back to `~`.

    A report is meant to be pasted somewhere, and a home directory carries the
    username with it.

    """
    if path is None:
        return 'not found'
    path = str(path)
    home = _home()
    if home and (path == home or path.startswith(home + os.sep)):
        return '~' + path[len(home):]
    return path


def _version(report):
    from ..utils import get_installation_version

    report.add('The Bleep', get_installation_version())
    report.add('Python', '{} ({})'.format(
        sys.version.split()[0], tidy(sys.executable)))


def _platform(report):
    # `platform` is not on any hot path and this is the only thing that wants
    # it, so it arrives here.
    import platform

    report.add('Platform', '{} {} ({})'.format(
        platform.system(), platform.release(), platform.machine()))


def _how_the_shell_was_found():
    if os.environ.get('TB_SHELL'):
        return 'from TB_SHELL'
    return 'from the process tree'


def _shell(report):
    from ..shells import shell

    report.add('Shell', '{} ({})'.format(
        shell.info(), _how_the_shell_was_found()))

    if type(shell).__name__ == 'Generic':
        report.add(
            'Shell support', 'generic', WARN,
            'The shell was not recognised, so only the rules that do not care'
            ' which shell you are in will work. Try --shell to say.')
        return

    try:
        too_old = shell.unsupported_version()
    except Exception:                                            # pragma: no cover
        too_old = None
    if too_old:
        report.add('Shell version', 'too old', WARN, too_old)


# The startup files worth looking in for an alias, per shell driver. Only the
# file the shell itself would read: finding the line in some other file would
# be a worse answer than not finding it.
def _integration(report):
    from ..shells import shell

    try:
        configuration = shell.how_to_configure()
    except Exception:                                        # pragma: no cover
        configuration = None

    if configuration is None:
        report.add('Integration', 'no startup file known for this shell', NOTE)
        return

    from ..system import expanduser

    path = expanduser(configuration.path)
    if not path.is_file():
        report.add('Integration', '{} does not exist'.format(
            tidy(configuration.path)), WARN,
            'Run `thebleep --alias-loader >> {}` and open a new shell.'.format(
                configuration.path))
        return

    try:
        with path.open('r', encoding='utf-8', errors='ignore') as handle:
            content = handle.read()
    except OSError:                                          # pragma: no cover
        report.add('Integration', 'cannot read {}'.format(
            tidy(path)), WARN)
        return

    # What is looked for, and all that is looked for. The file is somebody's
    # shell configuration and none of the rest of it is reported.
    # A clone's alias names an interpreter and a file rather than `thebleep`,
    # so the flag is what identifies the line, not the program in front of it.
    # Matching `thebleep --alias-loader` reported a working zero-install setup
    # as "named, but not as an alias".
    if '--alias-loader' in content:
        report.add('Integration', 'alias loader in {}'.format(tidy(path)))
    elif '--alias' in content or 'thebleep -a' in content:
        report.add('Integration', 'alias in {}'.format(tidy(path)), NOTE,
                   'The loader defines the alias on first use instead, so'
                   ' opening a shell runs no Python: `thebleep'
                   ' --alias-loader`.')
    elif 'thebleep' in content:
        report.add('Integration', 'thebleep named in {}, but not as an'
                   ' alias'.format(tidy(path)), NOTE)
    else:
        report.add('Integration', 'not in {}'.format(tidy(path)), WARN,
                   'Run `thebleep --alias-loader >> {}` and open a new'
                   ' shell.'.format(configuration.path))


def _executable(report):
    from ..utils import which

    running = os.path.realpath(sys.argv[0]) if sys.argv and sys.argv[0] else ''
    found = which('thebleep')
    report.add('Executable', tidy(running or 'unknown'))

    from .. import invocation

    # An alias that names a file does not go through `PATH`, so `thebleep` not
    # being on it is the arrangement working rather than a fault. Warning
    # anyway put "add the directory above to PATH" under a zero-install clone,
    # two lines below the path it was already running.
    reached_by_name = invocation.command() == invocation.ENTRY_POINT

    if not reached_by_name:
        report.add('Reached by', invocation.command(), NOTE,
                   'A checkout, so the alias names it directly and does not'
                   ' need `thebleep` on PATH. `git pull` is the upgrade.')
    elif found is None:
        report.add('On PATH', 'thebleep is not on PATH', WARN,
                   'The alias calls `thebleep` by name, so it has to be'
                   ' findable. Add the directory above to PATH.')
    elif running and os.path.realpath(found) != running:
        report.add('On PATH', tidy(found), WARN,
                   'That is a different copy from the one now running, so your'
                   ' shell is using the other one. Two installations, or an'
                   ' old one left behind.')
    else:
        report.add('On PATH', 'yes')


def _user_dir():
    """Where settings live, without creating anything to find out."""
    from ..conf import settings

    return settings._get_user_dir_path()


def _config(report):
    user_dir = _user_dir()
    path = user_dir.joinpath('settings.py')
    if not path.is_file():
        report.add('Config', '{} (none yet, defaults in use)'.format(
            tidy(path)), NOTE)
        return

    # Compiled and run the same way a correction runs it, so that a settings
    # file which would break one breaks this too -- that is the point.
    namespace = {'__file__': str(path), '__name__': 'settings'}
    try:
        with open(str(path), 'rb') as handle:
            exec(compile(handle.read(), str(path), 'exec'), namespace)
    except Exception as error:
        report.add('Config', '{} does not load'.format(tidy(path)), WARN,
                   '{}: {}. Every setting in the file is being ignored.'.format(
                       type(error).__name__, error))
        return

    # The names that are set, and not one of the values: a settings file holds
    # paths and command names, and this is meant to be pasteable.
    named = sorted(name for name in const.DEFAULT_SETTINGS if name in namespace)
    report.add('Config', '{} ({})'.format(
        tidy(path),
        '{} set: {}'.format(len(named), ', '.join(named)) if named
        else 'nothing overridden'))

    unknown = sorted(name for name in namespace
                     if not name.startswith('__')
                     and name not in const.DEFAULT_SETTINGS)
    if unknown:
        report.add('Config extras', ', '.join(unknown), NOTE,
                   'Not settings The Bleep knows, so they do nothing.'
                   ' A misspelling looks exactly like this.')

    _configured_rules(report, namespace.get('rules'))


def _configured_rules(report, rules):
    """Whether a `rules` list in the settings file leaves anything enabled.

    Naming rules by hand replaces the default set rather than adding to it, so a
    list of one misspelling is a list of no rules -- and the only symptom is that
    nothing is ever corrected again, which looks like the tool being broken
    rather than like the setting it is.

    `DEFAULT_RULES` is expanded here the same way loading the file expands it, so
    that this agrees with what a correction will actually do.

    """
    if not isinstance(rules, list):
        return

    from ..conf import settings

    named = settings._expand_default_rules(rules)
    if const.ALL_ENABLED in named:
        return

    known = _rule_names()
    unknown = sorted(name for name in named
                     if isinstance(name, str) and name not in known)
    if not [name for name in named if name in known]:
        report.add('Rules enabled', 'none', WARN,
                   'Your `rules` names no rule that exists, and naming rules'
                   ' replaces the default set rather than adding to it, so'
                   ' nothing can be corrected. Add `DEFAULT_RULES` to the list'
                   ' to keep the rest.')
    elif unknown:
        report.add('Rules enabled', '{} of the {} named'.format(
            len(named) - len(unknown), len(named)), NOTE,
            'No such rule: {}. A misspelling looks exactly like this.'.format(
                ', '.join(unknown)))


def _rule_directories():
    """Every directory this installation would load rules from."""
    yield os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'rules')
    yield str(_user_dir().joinpath('rules'))
    for path in sys.path:
        try:
            entries = list(os.scandir(path))
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith('thebleep_contrib_'):
                yield os.path.join(entry.path, 'rules')


def _rule_files(directory):
    try:
        return [entry.name for entry in os.scandir(str(directory))
                if entry.name.endswith('.py')
                and entry.name != '__init__.py']
    except OSError:
        return []


def _count_rules(directory):
    return len(_rule_files(directory))


def _rule_names():
    """The names of every rule on this machine, as a `rules` setting spells
    them."""
    return {name[:-3] for directory in _rule_directories()
            for name in _rule_files(directory)}


def _rules(report):
    directories = list(_rule_directories())
    bundled, user = directories[0], directories[1]

    counts = ['{} bundled'.format(_count_rules(bundled))]
    user_count = _count_rules(user)
    if user_count:
        counts.append('{} of your own'.format(user_count))

    contrib = sum(_count_rules(directory) for directory in directories[2:])
    if contrib:
        counts.append('{} from packages'.format(contrib))

    report.add('Rules', ', '.join(counts))


def _rule_health(report):
    """Whether every rule still loads and still answers.

    Three rules were found dead against real output in one afternoon --
    `git_add` matched a message with a full stop git had dropped, `hostscli`
    read the whole error sentence instead of the name in it, and
    `git_rebase_merge_dir` found its answer by counting lines from the end.
    Each had been dead for releases, because `Rule.is_match` and
    `Rule.get_corrected_commands` catch what a rule raises: the only symptom is
    a rule that never fires, which is indistinguishable from a rule that had
    nothing to say.

    What is checkable from here is narrower than that, and worth having anyway:
    a rule that will not import, and a rule that raises on the plainest input
    there is. Neither can be seen any other way without reading the rule.

    The probes are shapes a correction really produces. `Command('', '')` is
    not one -- `Command.from_raw_script` refuses an empty script -- and using it
    reported four rules as broken for indexing `script_parts[0]`, which is an
    index they are entitled to.

    """
    from .. import corrector
    from ..types import Command

    try:
        rules = corrector.get_rules()
    except Exception as error:                               # pragma: no cover
        report.add('Rule health', 'the rules could not be loaded', WARN,
                   '{}: {}'.format(type(error).__name__, error))
        return

    probes = (Command('x', ''),
              Command('git x', 'error: something'),
              Command('x y z', 'not found'))

    broken = []
    for rule in rules:
        for probe in probes:
            try:
                rule.match(probe)
            except Exception as error:                       # noqa: BLE001
                broken.append('{} ({})'.format(rule.name,
                                               type(error).__name__))
                break

    # "enabled", because the line above this one counts what is *bundled* and
    # these are the ones your settings actually load. Two different numbers
    # both labelled "rules" read as a contradiction in a diagnostic somebody is
    # scanning for what is wrong.
    if not broken:
        report.add('Rule health',
                   '{} enabled, none raising'.format(len(rules)))
        return

    report.add('Rule health',
               '{} of {} enabled rules raise on a plain command'.format(
                   len(broken), len(rules)),
               WARN,
               'These never fire, and nothing says so: ' + ', '.join(broken))


def _rule_pack(report):
    from .. import cachefile, rulepack

    if rulepack._is_disabled():
        report.add('Rule pack', 'switched off by THEBLEEP_NO_RULE_PACK', NOTE,
                   'Corrections still work; they just load every rule.')
        return

    path = rulepack._cache_path()
    # Counted the way the rules above are counted, so that two numbers about
    # the same rules agree. Two things stop them agreeing on their own: the pack
    # has an entry for the package's `__init__.py`, which is not a rule, and it
    # is keyed by absolute path -- so a second installation writing the same
    # pack, in the same cache directory under the same interpreter, leaves
    # entries in it for rule files this installation will never load. Reporting
    # "346 rules cached" against "173 bundled" describes a machine with two
    # copies on it and reads as a number that has gone wrong.
    ours = {os.path.normcase(os.path.abspath(directory))
            for directory in _rule_directories()}
    entries, elsewhere = [], 0
    for key in rulepack._read_pack():
        if key.endswith('__init__.py'):
            continue
        if os.path.normcase(os.path.dirname(os.path.abspath(key))) in ours:
            entries.append(key)
        else:
            elsewhere += 1

    if not entries:
        report.add('Rule pack', '{} (not built yet)'.format(tidy(path)), NOTE,
                   'The next correction builds it.')
    else:
        report.add('Rule pack', '{} ({} rules cached)'.format(
            tidy(path), len(entries)))
    if elsewhere:
        report.add('Rule pack extras', '{} entries from somewhere else'.format(
            elsewhere), NOTE,
            'Another installation shares this cache. Harmless -- they are'
            ' keyed by path and never loaded from here.'
            ' `thebleep --clear-cache` clears it.')

    directory = cachefile.directory()
    if not os.access(str(directory), os.W_OK) and directory.exists():
        report.add('Cache', '{} is not writable'.format(tidy(directory)), WARN,
                   'Every correction will recompile every rule.')


def _capture(report):
    """Whether a correction can read the output without running anything."""
    from ..shells import shell

    if os.environ.get(const.SHELL_LOGGER_SOCKET_ENV):
        report.add('Replayless capture', 'an external shell logger is'
                   ' listening')
        return

    if os.environ.get('THEBLEEP_INSTANT_MODE', '').lower() == 'true':
        report.add('Replayless capture', 'instant mode is running')
        return

    if shell.supports_instant_mode():
        report.add('Replayless capture', 'available, not switched on', NOTE,
                   'See --enable-experimental-instant-mode.')
    else:
        report.add('Replayless capture', 'not available for this shell', NOTE)


def _editing(report):
    from ..shells import shell

    if not shell.can_run_corrections():
        report.add('Corrections', 'always go to your command line to submit',
                   NOTE)
        return

    if shell.can_edit_buffer():
        report.add('Editing', 'supported by this shell (tab at the prompt)')
    else:
        report.add('Editing', 'not available for this shell', NOTE,
                   'No supported way to write its line editor.')


def _leftovers(report):
    """A The Fuck configuration nobody copied over."""
    from ..system import expanduser

    config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
    candidates = [expanduser(os.path.join(config_home, 'thefuck')),
                  expanduser(os.path.join('~', '.thefuck'))]
    found = [path for path in candidates if path.is_dir()]
    if not found:
        return

    ours = _user_dir()
    if ours.joinpath('settings.py').is_file():
        report.add('The Fuck', '{} is still there'.format(tidy(found[0])),
                   NOTE, 'Nothing reads it any more; yours is above.')
    else:
        report.add('The Fuck', '{} has not been copied over'.format(
            tidy(found[0])), WARN,
            'Your settings and your own rules are in there: '
            '`cp -r {} {}`.'.format(tidy(found[0]), tidy(ours)))


def _dependencies(report):
    """The two packages that have to be there, and what breaks without each."""
    missing = []
    for name, what in (('psutil', 'working out which shell you are in'),
                       ('pyte', 'reading recorded output in instant mode')):
        try:
            __import__(name)
        except ImportError:
            missing.append('{} (needed for {})'.format(name, what))

    if missing:
        report.add('Dependencies', '; '.join(missing), WARN,
                   'Reinstall The Bleep, or install them yourself.')


def _environment(report):
    """Which of our own variables are set. The names, never the values."""
    names = sorted(const.ENV_TO_ATTR)
    set_here = [name for name in names if name in os.environ]
    if set_here:
        report.add('Environment', ', '.join(set_here), NOTE,
                   'These override your settings file.')


CHECKS = (_version, _platform, _shell, _integration, _executable, _config,
          _rules, _rule_health, _rule_pack, _capture, _editing, _dependencies, _leftovers,
          _environment)


def doctor():
    """Prints what is installed, what is configured, and what is wrong."""
    report = Report()
    for check in CHECKS:
        try:
            check(report)
        except Exception as error:                           # pragma: no cover
            report.add(check.__name__.strip('_').replace('_', ' ').title(),
                       'could not be checked', WARN,
                       '{}: {}'.format(type(error).__name__, error))

    logs.doctor_report(report.lines)
    return 1 if report.problems else 0
