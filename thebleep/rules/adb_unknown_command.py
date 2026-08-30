from thebleep.utils import (command_word_index, get_closest, is_app,
                            replace_argument)


_ADB_COMMANDS = (
    'backup',
    'bugreport',
    'connect',
    'devices',
    'disable-verity',
    'disconnect',
    'enable-verity',
    'emu',
    'forward',
    'get-devpath',
    'get-serialno',
    'get-state',
    'install',
    'install-multiple',
    'jdwp',
    'keygen',
    'kill-server',
    'logcat',
    'pull',
    'push',
    'reboot',
    'reconnect',
    'restore',
    'reverse',
    'root',
    'run-as',
    'shell',
    'sideload',
    'start-server',
    'sync',
    'tcpip',
    'uninstall',
    'unroot',
    'usb',
    'wait-for',
)


def match(command):
    if not (is_app(command, 'adb')
            and command.output.startswith('Android Debug Bridge version')):
        return False

    return _get_closest_command(command.script_parts) is not None


def _get_closest_command(script_parts):
    for arg in _command_arguments(script_parts):
        return get_closest(arg, _ADB_COMMANDS, fallback_to_first=False)


def _command_arguments(script_parts):
    """Arguments after adb's options, with option values skipped."""
    start = command_word_index(script_parts)
    index = start + 1
    while index < len(script_parts):
        arg = script_parts[index]
        if arg in ('-s', '-H', '-P', '-L'):
            index += 2
        elif arg.startswith('-'):
            index += 1
        else:
            yield arg
            index += 1


def get_new_command(command):
    for arg in _command_arguments(command.script_parts):
        adb_cmd = get_closest(arg, _ADB_COMMANDS, fallback_to_first=False)
        if adb_cmd is None:
            return []
        return replace_argument(command.script, arg, adb_cmd)

    return []
