import os
import sys
from warnings import warn
from . import const
from .system import Path, expanduser, writable


def load_source(name, pathname, _file=None):
    # Only a rule that is not in the pack, or a user's own settings file, gets
    # here. Importing the machinery to load one costs every correction that
    # never needs it.
    import importlib.util

    module_spec = importlib.util.spec_from_file_location(name, pathname)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


# Which settings are yes-or-no questions, read off the defaults rather than
# listed by hand. The hand-written list left `repeat` out, and a setting missing
# from it kept the environment variable's *string* -- so `THEBLEEP_REPEAT=false`,
# a non-empty string and therefore true, turned repeat mode on and appended
# `bleep --repeat --force-command ...` to every accepted suggestion. Anything
# whose default is a bool is now a bool, and a setting added later cannot be
# forgotten here.
BOOLEANS_BY_DEFAULT = frozenset(
    name for name, value in const.DEFAULT_SETTINGS.items()
    if isinstance(value, bool))


class Settings(dict):
    def __getattr__(self, item):
        return self.get(item)

    def __setattr__(self, key, value):
        self[key] = value

    def init(self, args=None):
        """Fills `settings` with values from `settings.py` and env."""
        from .logs import exception

        # Both of these *create* things, and neither is needed to correct a
        # command. They used to be outside the error handling, so a config
        # location that could not be written to -- a read-only home, a
        # container mount, an `XDG_CONFIG_HOME` pointing at a file -- was not a
        # missing settings file, it was a `NotADirectoryError` out of the
        # middle of every correction and every `--alias`, which is to say a
        # shell that could not start. Defaults are a complete answer; writing
        # them down is a convenience.
        self._setup_user_dir()

        try:
            self._init_settings_file()
        except Exception:
            from .logs import debug

            debug("Can't create a settings file; using defaults")

        try:
            self.update(self._settings_from_file())
        except OSError:
            # No settings file, or nowhere it could have been: not a problem
            # worth a traceback for, because everything in it has a default. A
            # settings file that exists and *raises* still gets one, below --
            # that is a mistake in it, and the user wants to know.
            from .logs import debug

            debug("No settings file to read; using defaults")
        except Exception:
            exception("Can't load settings from file", sys.exc_info())

        try:
            self.update(self._settings_from_env())
        except Exception:
            exception("Can't load settings from env", sys.exc_info())

        self.update(self._settings_from_args(args))

    def _init_settings_file(self):
        settings_path = self.user_dir.joinpath('settings.py')
        if not settings_path.is_file():
            with settings_path.open(mode='w') as settings_file:
                settings_file.write(const.SETTINGS_HEADER)
                for setting in const.DEFAULT_SETTINGS.items():
                    settings_file.write(u'# {} = {}\n'.format(*setting))

    def _get_user_dir_path(self):
        """Returns Path object representing the user config resource"""
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
        # `writable`, because this is somewhere we create and write to: with no
        # home directory to expand `~` against, the alternative is a directory
        # named `~` in whatever the working directory happens to be.
        user_dir = writable(expanduser(Path(xdg_config_home, 'thebleep')),
                            'config')
        legacy_user_dir = expanduser(Path('~', '.thebleep'))

        # For backward compatibility use legacy '~/.thebleep' if it exists:
        if legacy_user_dir.is_dir():
            warn(u'Config path {} is deprecated. Please move to {}'.format(
                legacy_user_dir, user_dir))
            return legacy_user_dir
        else:
            return user_dir

    def _setup_user_dir(self):
        """Settles on the user config dir, and creates it if it can.

        Creating it is best-effort. `self.user_dir` is set either way, so a
        settings file that is there gets read and one that is not gets
        defaults -- what does not happen is a failure to make a directory
        ending a correction.

        """
        user_dir = self._get_user_dir_path()
        self.user_dir = user_dir

        rules_dir = user_dir.joinpath('rules')
        try:
            if not rules_dir.is_dir():
                rules_dir.mkdir(parents=True)
        except OSError:
            from .logs import debug

            debug(u'Could not create {}; using defaults'.format(rules_dir))

    def _settings_from_file(self):
        """Loads settings from file.

        Run rather than imported. `load_source` builds a real module through
        `importlib.util`, and a settings file is a handful of assignments whose
        names are all this reads back -- so the module was machinery nobody
        used, and `importlib.util` (with `contextlib` behind it) was imported on
        every correction to get it. A settings file that imports something of
        its own still works: this is the same compile and the same execution,
        into a namespace instead of a module.

        """
        path = str(self.user_dir.joinpath('settings.py'))
        with open(path, 'rb') as handle:
            source = handle.read()

        namespace = {'__file__': path, '__name__': 'settings'}
        exec(compile(source, path, 'exec'), namespace)
        from_file = {key: namespace[key]
                     for key in const.DEFAULT_SETTINGS.keys()
                     if key in namespace}
        for key in ('rules', 'exclude_rules'):
            if key in from_file:
                from_file[key] = self._expand_default_rules(from_file[key])
        return from_file

    def _expand_default_rules(self, rules):
        """A rules list with the `DEFAULT_RULES` sentinel expanded.

        The environment variable spells "and everything that is on by default"
        as the string `DEFAULT_RULES`, and every example spells it that way. In
        a settings file the same string used to mean a rule of that name, of
        which there is none -- so `rules = ['DEFAULT_RULES', 'python_module_error']`
        enabled one rule and disabled the other 172, and the only symptom was
        that nothing was ever corrected again. It means the same thing in both
        places now.

        A settings file is Python, so `from thebleep.const import DEFAULT_RULES`
        and splicing the real constant in works as well, and always did.

        """
        if not isinstance(rules, list) or 'DEFAULT_RULES' not in rules:
            return rules
        return [item for rule in rules
                for item in (const.DEFAULT_RULES if rule == 'DEFAULT_RULES'
                             else [rule])]

    def _rules_from_env(self, val):
        """Transforms rules list from env-string to python."""
        return self._expand_default_rules(val.split(':'))

    def _priority_from_env(self, val):
        """Gets priority pairs from env."""
        for part in val.split(':'):
            try:
                rule, priority = part.split('=')
                yield rule, int(priority)
            except ValueError:
                continue

    # What counts as yes and what counts as no. It used to be `== 'true'` and
    # anything else at all, so `THEBLEEP_DEBUG=1` quietly meant no.
    BOOLEANS = {'true': True, 'yes': True, 'on': True, '1': True,
                'false': False, 'no': False, 'off': False, '0': False}

    # A timeout of zero means never waiting; a history limit or a number of
    # suggestions of zero means the setting does nothing, which nobody sets on
    # purpose and which reads as the feature being broken.
    COUNTS = {'wait_command': 0, 'wait_slow_command': 0,
              'history_limit': 1, 'num_close_matches': 1}

    def _number_from_env(self, attr, val):
        try:
            number = int(val)
        except ValueError:
            raise ValueError('{!r} is not a number'.format(val))
        least = self.COUNTS[attr]
        if number < least:
            raise ValueError('{} is less than {}'.format(number, least))
        return number

    def _bool_from_env(self, val):
        try:
            return self.BOOLEANS[val.strip().lower()]
        except KeyError:
            raise ValueError(
                '{!r} is neither true nor false'.format(val))

    def _val_from_env(self, env, attr):
        """Transforms env-strings to python."""
        val = os.environ[env]
        if attr in ('rules', 'exclude_rules'):
            return self._rules_from_env(val)
        elif attr == 'priority':
            return dict(self._priority_from_env(val))
        elif attr in self.COUNTS:
            return self._number_from_env(attr, val)
        elif attr in BOOLEANS_BY_DEFAULT:
            return self._bool_from_env(val)
        elif attr in ('slow_commands', 'excluded_search_path_prefixes'):
            return val.split(':')
        else:
            return val

    def _settings_from_env(self):
        """Loads settings from env, one variable at a time.

        One at a time on purpose. This was a comprehension, so one value that
        would not parse -- `THEBLEEP_WAIT_COMMAND=abc` -- raised out of the whole
        thing, the caller's `update` never happened, and *every* environment
        setting was silently dropped: colours came back on, excluded rules came
        back with them. A setting that cannot be understood now costs that
        setting, says so, and costs nothing else.

        """
        from .logs import warn

        settings = {}
        for env, attr in sorted(const.ENV_TO_ATTR.items()):
            if env not in os.environ:
                continue
            try:
                settings[attr] = self._val_from_env(env, attr)
            except ValueError as error:
                warn(u'Ignoring {}: {}.'.format(env, error))
        return settings

    def _settings_from_args(self, args):
        """Loads settings from args."""
        if not args:
            return {}

        from_args = {}
        if args.yes:
            from_args['require_confirmation'] = not args.yes
            # `--yes` is consent given for this run, so it covers running the
            # previous command again as well as the correction.
            from_args['confirm_replay'] = False
        if args.debug:
            from_args['debug'] = args.debug
        if args.repeat:
            from_args['repeat'] = args.repeat
        if args.edit:
            from_args['edit'] = args.edit
        if args.explain:
            from_args['explain'] = args.explain
        return from_args


# Settings whose *values* are nobody else's business. `env` is where people
# put tokens -- it is handed to the replayed command as its environment -- and
# the issue template asks for debug output to be pasted into a bug report.
SECRET = frozenset(('env',))


def redacted(values):
    """`values` with the secret ones reduced to their names.

    `fix_command` prints the whole settings object under `--debug`, and
    `Settings` is a plain dict, so it printed `{'env': {'API_TOKEN':
    'super-secret-value'}}` -- verified, and the changelog claimed otherwise
    because only the *replay* logger had been fixed. `--doctor` is the output
    written to be safe to paste; debug output is a copy of what happened and
    cannot be, but it does not have to hand over a token to say what it did.

    """
    shown = {}
    for name, value in values.items():
        if name in SECRET and isinstance(value, dict):
            shown[name] = sorted(value)
        elif name in SECRET and value:
            shown[name] = '<set>'
        else:
            shown[name] = value
    return shown


settings = Settings(const.DEFAULT_SETTINGS)
