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


class Settings(dict):
    def __getattr__(self, item):
        return self.get(item)

    def __setattr__(self, key, value):
        self[key] = value

    def init(self, args=None):
        """Fills `settings` with values from `settings.py` and env."""
        from .logs import exception

        self._setup_user_dir()
        self._init_settings_file()

        try:
            self.update(self._settings_from_file())
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
        """Returns user config dir, create it when it doesn't exist."""
        user_dir = self._get_user_dir_path()

        rules_dir = user_dir.joinpath('rules')
        if not rules_dir.is_dir():
            rules_dir.mkdir(parents=True)
        self.user_dir = user_dir

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
        return {key: namespace[key]
                for key in const.DEFAULT_SETTINGS.keys()
                if key in namespace}

    def _rules_from_env(self, val):
        """Transforms rules list from env-string to python."""
        val = val.split(':')
        if 'DEFAULT_RULES' in val:
            val = const.DEFAULT_RULES + [rule for rule in val if rule != 'DEFAULT_RULES']
        return val

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
        elif attr in ('require_confirmation', 'no_colors', 'debug',
                      'alter_history', 'instant_mode', 'confirm_replay',
                      'edit', 'explain'):
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


settings = Settings(const.DEFAULT_SETTINGS)
