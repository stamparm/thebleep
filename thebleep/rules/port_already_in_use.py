import re
from subprocess import Popen, PIPE
from thebleep.utils import memoize, which
from thebleep.shells import shell

enabled_by_default = bool(which('lsof'))

patterns = [r"bind on address \('.*', (?P<port>\d+)\)",
            r'Unable to bind [^ ]*:(?P<port>\d+)',
            r"can't listen on port (?P<port>\d+)",
            r'listen EADDRINUSE [^ ]*:(?P<port>\d+)']


@memoize
def _get_pid_by_port(port):
    proc = Popen(['lsof', '-i', ':{}'.format(port)], stdout=PIPE)
    lines = proc.stdout.read().decode().split('\n')
    if len(lines) > 1:
        columns = lines[1].split()
        # A pid, or nothing. `kill {}` is built from this and handed to the
        # shell, so a warning line where the header was expected must not
        # become part of a command.
        if len(columns) > 1 and columns[1].isdigit():
            return columns[1]
    return None


@memoize
def _get_used_port(command):
    for pattern in patterns:
        matched = re.search(pattern, command.output)
        if matched:
            return matched.group('port')


def match(command):
    port = _get_used_port(command)
    return port and _get_pid_by_port(port)


def get_new_command(command):
    port = _get_used_port(command)
    pid = _get_pid_by_port(port)
    return shell.and_(u'kill {}'.format(pid), command.script)
