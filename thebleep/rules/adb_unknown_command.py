from thebleep.utils import is_app, get_closest, replace_argument


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
    for idx, arg in enumerate(script_parts[1:]):
        # allowed params to ADB are a/d/e/s/H/P/L where s, H, P and L take
        # additional args, for example `adb -s 111 logcat`.
        if not arg.startswith('-') and script_parts[idx] not in (
                '-s', '-H', '-P', '-L'):
            return get_closest(arg, _ADB_COMMANDS, fallback_to_first=False)


def get_new_command(command):
    for idx, arg in enumerate(command.script_parts[1:]):
        if not arg.startswith('-') and command.script_parts[idx] not in (
                '-s', '-H', '-P', '-L'):
            adb_cmd = get_closest(arg, _ADB_COMMANDS,
                                  fallback_to_first=False)
            if adb_cmd is None:
                return []
            return replace_argument(command.script, arg, adb_cmd)

    return []
