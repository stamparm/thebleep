import os
import re
from thebleep.specific.sudo import sudo_support
from thebleep.utils import get_closest, replace_command
from thebleep.utils import for_app
from thebleep.specific.brew import get_brew_repository, brew_available

BREW_CMD_PATH = '/Library/Homebrew/cmd'
TAP_PATH = '/Library/Taps'
TAP_CMD_PATH = '/%s/%s/cmd'

# `Error: Unknown command: brew instaa` today, and `Error: Invalid usage:` in
# front of it when brew has a suggestion of its own to add. Older versions left
# the `brew ` out and named the command on its own.
UNKNOWN_COMMAND = re.compile(r'Unknown command: (?:brew )?([\w.-]+)')

enabled_by_default = brew_available


def _get_brew_commands(brew_repository):
    """To get brew default commands on local environment"""
    brew_cmd_path = brew_repository + BREW_CMD_PATH

    return [name[:-3] for name in os.listdir(brew_cmd_path)
            if name.endswith(('.rb', '.sh'))]


def _get_brew_tap_specific_commands(brew_repository):
    """To get tap's specific commands
    https://github.com/Homebrew/homebrew/blob/master/Library/brew.rb#L115"""
    commands = []
    brew_taps_path = brew_repository + TAP_PATH

    for user in _get_directory_names_only(brew_taps_path):
        taps = _get_directory_names_only(brew_taps_path + '/%s' % user)

        # Brew Taps's naming rule
        # https://github.com/Homebrew/homebrew/blob/master/share/doc/homebrew/brew-tap.md#naming-conventions-and-limitations
        taps = (tap for tap in taps if tap.startswith('homebrew-'))
        for tap in taps:
            tap_cmd_path = brew_taps_path + TAP_CMD_PATH % (user, tap)

            if os.path.isdir(tap_cmd_path):
                commands += (name.replace('brew-', '').replace('.rb', '')
                             for name in os.listdir(tap_cmd_path)
                             if _is_brew_tap_cmd_naming(name))

    return commands


def _is_brew_tap_cmd_naming(name):
    return name.startswith('brew-') and name.endswith('.rb')


def _get_directory_names_only(path):
    return [d for d in os.listdir(path)
            if os.path.isdir(os.path.join(path, d))]


def _brew_commands():
    brew_repository = get_brew_repository()
    if brew_repository:
        try:
            return (_get_brew_commands(brew_repository)
                    + _get_brew_tap_specific_commands(brew_repository))
        except OSError:
            pass

    # Failback commands for testing (Based on Homebrew 0.9.5)
    return ['info', 'home', 'options', 'install', 'uninstall',
            'search', 'list', 'update', 'upgrade', 'pin', 'unpin',
            'doctor', 'create', 'edit', 'cask']


def _get_broken_command(command):
    found = UNKNOWN_COMMAND.search(command.output)
    return found and found.group(1)


@sudo_support
@for_app('brew')
def match(command):
    broken_cmd = _get_broken_command(command)
    return bool(broken_cmd and get_closest(
        broken_cmd, _brew_commands(), fallback_to_first=False))


@sudo_support
def get_new_command(command):
    return replace_command(command, _get_broken_command(command),
                           _brew_commands())
