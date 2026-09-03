import re
from thebleep.shells import shell

patterns = ['permission denied',
            'eacces',
            'pkg: insufficient privileges',
            'you cannot perform this operation unless you are root',
            'non-root users cannot',
            'operation not permitted',
            'not super-user',
            'superuser privilege',
            'root privilege',
            'this command has to be run under the root user.',
            'this operation requires root.',
            'requested operation requires superuser privilege',
            'must be run as root',
            'must run as root',
            'must be superuser',
            'must be root',
            'need to be root',
            'need root',
            'needs to be run as root',
            'only root can ',
            'you don\'t have access to the history db.',
            'authentication is required',
            'edspermissionerror',
            'you don\'t have write permissions',
            'use `sudo`',
            'sudorequirederror',
            'error: insufficient privileges',
            'updatedb: can not open a temporary file']


def match(command):
    if command.script_parts and '&&' not in command.script_parts and command.script_parts[0] == 'sudo':
        return False

    # Lowered once. It was inside the loop, so a command that printed a megabyte
    # had it copied twenty-eight times before this rule gave up on it.
    output = command.output.lower()
    return any(pattern in output for pattern in patterns)


# `sudo` where a command starts, rather than anywhere at all: the word could
# just as well be an argument or part of a quoted string.
LEADING_SUDO = re.compile(r'(^|\|\||&&|;|\|)(\s*)sudo\s+')


def _without_sudo(script):
    """Drops `sudo` from the front of every command in `script`.

    Works on the script as typed rather than on its parts, so that the user's
    own quoting survives to the shell that will run it.

    """
    previous = None
    while previous != script:
        previous = script
        script = LEADING_SUDO.sub(r'\1\2', script)
    return script


def _privilege_command():
    """`sudo`, or `doas` on a machine that has doas and no sudo: OpenBSD,
    and the Linux and BSD boxes that chose it. `sudo` still wins where both
    are installed, because that is what the matrix's rows and most people's
    fingers expect."""
    from thebleep.utils import which

    if not which('sudo') and which('doas'):
        return 'doas'
    return 'sudo'


def get_new_command(command):
    # Anything that goes inside `sh -c` is run again, by root this time, so it
    # is quoted as one argument: without that, a quote in the script ends the
    # `sh -c` argument early and the rest of the line runs as separate
    # commands, and text the user had quoted as data becomes code.
    become = _privilege_command()
    if '&&' in command.script:
        return u'{} sh -c {}'.format(become, shell.quote(
            _without_sudo(command.script)))
    elif '>' in command.script:
        return u'{} sh -c {}'.format(become, shell.quote(command.script))
    else:
        return u'{} {}'.format(become, command.script)
