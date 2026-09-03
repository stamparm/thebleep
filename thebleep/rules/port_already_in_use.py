import re
from thebleep.utils import memoize, which, tool_lines
from thebleep.shells import shell

enabled_by_default = bool(which('lsof'))

patterns = [r"bind on address \('.*', (?P<port>\d+)\)",
            r'Unable to bind [^ ]*:(?P<port>\d+)',
            r"can't listen on port (?P<port>\d+)",
            r'listen EADDRINUSE [^ ]*:(?P<port>\d+)']


@memoize
def _get_pid_by_port(port):
    # `lsof` against a wedged NFS mount or an unresponsive filesystem is the
    # textbook hang, and this one runs from `match` -- so on the hot path of
    # every failed command whose output mentions a port.
    #
    # `-sTCP:LISTEN`, for the process *listening* on the port: without it the
    # first row can be a client connected to it -- a browser -- and that is
    # what `kill` would have been aimed at. `-t` prints pids alone.
    for line in tool_lines(['lsof', '-t', '-i', ':{}'.format(port),
                            '-sTCP:LISTEN']):
        # A pid, or nothing. `kill {}` is built from this and handed to the
        # shell, so a warning line must not become part of a command.
        if line.strip().isdigit():
            return line.strip()
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
