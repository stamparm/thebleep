# -*- encoding: utf-8 -*-

import os


def get_alias():
    """The name the alias was defined under, `bleep` unless told otherwise."""
    return os.environ.get('TB_ALIAS', 'bleep')


def can_edit():
    """Whether the alias that called us can put a command in the line editor.

    The alias sets this, not us: whether a correction can be handed back for
    editing depends on shell code that was written by whichever version of The
    Bleep defined the alias, and a shell started before an upgrade is still
    running the old one. Asking the environment means the offer is only made
    when the shell on the other end actually knows what to do with it.

    """
    return bool(os.environ.get('TB_CAN_EDIT'))


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
ACTION_EDIT = _GenConst('edit')
ACTION_EXPLAIN = _GenConst('explain')

# Tab, which is what asks for the suggestion to be handed to the line editor
# rather than run. It is the one obvious free key: `e` is already the colemak
# spelling of "previous", and the gesture matches what tab does everywhere else
# in a shell -- put something on the line for me to finish.
KEY_TAB = '\t'

# `?`, which asks why a suggestion is being offered. Free everywhere else, and
# the thing a shell user already presses when they want to be told something.
KEY_QUESTION = '?'

# The exit status that means "what is on stdout is to be edited, not run".
# The shell alias reads it and puts the command in the line editor; every other
# status keeps its old meaning, so an alias that predates this feature simply
# never sees it -- and `can_edit` above makes sure we never produce it for one.
EXIT_EDIT = 3

# Shell name, as the alias reports it in `TB_SHELL` and as `--shell` accepts
# it -> the class that drives that shell.
#
# It lives here rather than in `shells` because asking `shells` anything runs
# shell detection, and `--shell` exists precisely for the cases where detection
# is what went wrong. Validating a name must not first do the thing the name is
# there to skip.
SHELLS = {'bash': 'Bash',
          'fish': 'Fish',
          'zsh': 'Zsh',
          'csh': 'Tcsh',
          'tcsh': 'Tcsh',
          'nu': 'Nushell',
          'powershell': 'Powershell',
          'pwsh': 'Powershell'}

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
                    'edit': False,
                    'explain': False,
                    'instant_mode': False,
                    'num_close_matches': 3,
                    'confirm_replay': True,
                    'env': {'LC_ALL': 'C', 'LANG': 'C'},
                    'excluded_search_path_prefixes': [],
                    'auto_run_confidence': None,
                    'why_command': None,
                    'why_timeout': 30,
                    'warm_server': False}

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
               'THEBLEEP_EDIT': 'edit',
               'THEBLEEP_EXPLAIN': 'explain',
               'THEBLEEP_INSTANT_MODE': 'instant_mode',
               'THEBLEEP_NUM_CLOSE_MATCHES': 'num_close_matches',
               'THEBLEEP_CONFIRM_REPLAY': 'confirm_replay',
               'THEBLEEP_EXCLUDED_SEARCH_PATH_PREFIXES': 'excluded_search_path_prefixes',
               'THEBLEEP_AUTO_RUN_CONFIDENCE': 'auto_run_confidence',
               'THEBLEEP_WHY_COMMAND': 'why_command',
               'THEBLEEP_WHY_TIMEOUT': 'why_timeout',
               'THEBLEEP_WARM_SERVER': 'warm_server'}

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

# The kernel will not hand a program any single environment variable larger
# than 128K (MAX_ARG_STRLEN, 32 pages), and one pasted command that size among
# the last ten history entries used to make the alias fail outright with
# "Argument list too long" -- for that correction and for every one after it,
# until the entry fell out of the window. The alias asks the shell for a smaller
# window until what it has fits; see `shells.generic.fit_transport`.
#
# Counted in *characters*, because `${#var}` in bash and zsh counts characters,
# and the kernel's limit is in bytes. In a UTF-8 locale one character is up to
# four bytes, so the limit has to be a quarter of the budget for the two to
# agree: 32000 characters is at most 128000 bytes, which leaves room for the
# variable's name and the `=` inside 131072. A cap of 65536 characters looked
# right and was not -- a single 64000-character command of three-byte characters
# is 192000 bytes, passed the test, and still failed to exec.
#
# Refs: nvbn/thefuck#798
TRANSPORT_LIMIT = 32000
