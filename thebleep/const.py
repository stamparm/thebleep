# -*- encoding: utf-8 -*-

import os


def get_alias():
    """The name the alias was defined under, `bleep` unless told otherwise."""
    return os.environ.get('TB_ALIAS', 'bleep')


class _GenConst(object):
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return u'<const: {}>'.format(self._name)


KEY_UP = _GenConst('↑')
KEY_DOWN = _GenConst('↓')
KEY_CTRL_C = _GenConst('Ctrl+C')
KEY_CTRL_N = _GenConst('Ctrl+N')
KEY_CTRL_P = _GenConst('Ctrl+P')
KEY_ESCAPE = _GenConst('Esc')

KEY_MAPPING = {'\x0e': KEY_CTRL_N,
               '\x03': KEY_CTRL_C,
               '\x10': KEY_CTRL_P}

ACTION_SELECT = _GenConst('select')
ACTION_ABORT = _GenConst('abort')
ACTION_PREVIOUS = _GenConst('previous')
ACTION_NEXT = _GenConst('next')

ALL_ENABLED = _GenConst('All rules enabled')
DEFAULT_RULES = [ALL_ENABLED]
DEFAULT_PRIORITY = 1000

DEFAULT_SETTINGS = {'rules': DEFAULT_RULES,
                    'exclude_rules': [],
                    'wait_command': 3,
                    'require_confirmation': True,
                    'no_colors': False,
                    'debug': False,
                    'priority': {},
                    'history_limit': None,
                    'alter_history': True,
                    'wait_slow_command': 15,
                    'slow_commands': ['lein', 'react-native', 'gradle',
                                      './gradlew', 'vagrant'],
                    'repeat': False,
                    'instant_mode': False,
                    'num_close_matches': 3,
                    'env': {'LC_ALL': 'C', 'LANG': 'C', 'GIT_TRACE': '1'},
                    'excluded_search_path_prefixes': []}

ENV_TO_ATTR = {'THEBLEEP_RULES': 'rules',
               'THEBLEEP_EXCLUDE_RULES': 'exclude_rules',
               'THEBLEEP_WAIT_COMMAND': 'wait_command',
               'THEBLEEP_REQUIRE_CONFIRMATION': 'require_confirmation',
               'THEBLEEP_NO_COLORS': 'no_colors',
               'THEBLEEP_DEBUG': 'debug',
               'THEBLEEP_PRIORITY': 'priority',
               'THEBLEEP_HISTORY_LIMIT': 'history_limit',
               'THEBLEEP_ALTER_HISTORY': 'alter_history',
               'THEBLEEP_WAIT_SLOW_COMMAND': 'wait_slow_command',
               'THEBLEEP_SLOW_COMMANDS': 'slow_commands',
               'THEBLEEP_REPEAT': 'repeat',
               'THEBLEEP_INSTANT_MODE': 'instant_mode',
               'THEBLEEP_NUM_CLOSE_MATCHES': 'num_close_matches',
               'THEBLEEP_EXCLUDED_SEARCH_PATH_PREFIXES': 'excluded_search_path_prefixes'}

SETTINGS_HEADER = u"""# The Bleep settings file
#
# The rules are defined as in the example bellow:
#
# rules = ['cd_parent', 'git_push', 'python_command', 'sudo']
#
# The default values are as follows. Uncomment and change to fit your needs.
# See https://github.com/stamparm/thebleep#settings for more information.
#

"""

ARGUMENT_PLACEHOLDER = 'THEBLEEP_ARGUMENT_PLACEHOLDER'

CONFIGURATION_TIMEOUT = 60

USER_COMMAND_MARK = u'\u200B' * 10

LOG_SIZE_IN_BYTES = 1024 * 1024

LOG_SIZE_TO_CLEAN = 10 * 1024

DIFF_WITH_ALIAS = 0.5

SHELL_LOGGER_SOCKET_ENV = 'SHELL_LOGGER_SOCKET'

SHELL_LOGGER_LIMIT = 5
