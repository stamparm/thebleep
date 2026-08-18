import re
from thebleep.utils import for_app

commands = ('ssh', 'scp')


@for_app(*commands)
def match(command):
    # No `startswith` check: `for_app` has already established which command
    # this is, and does it without being fooled by `TERM=xterm-256color ssh`.
    patterns = (
        r'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!',
        r'WARNING: POSSIBLE DNS SPOOFING DETECTED!',
        r"Warning: the \S+ host key for '([^']+)' differs from the key for the IP address '([^']+)'",
    )

    return any(re.findall(pattern, command.output) for pattern in patterns)


def get_new_command(command):
    return command.script


def side_effect(old_cmd, command):
    offending_pattern = re.compile(
        r'(?:Offending (?:key for IP|\S+ key)|Matching host key) in ([^:]+):(\d+)',
        re.MULTILINE)
    offending = offending_pattern.findall(old_cmd.output)
    for filepath, lineno in offending:
        # Bytes, not text: this deletes one line from somebody's known_hosts
        # and writes the rest of it back, and the rest of it has to come out
        # exactly as it went in. Decoding it would mean guessing an encoding
        # for a file that has none, and guessing wrong either mangles the
        # lines being kept or refuses to read the file at all.
        with open(filepath, 'rb') as fh:
            lines = fh.readlines()
            del lines[int(lineno) - 1]
        with open(filepath, 'wb') as fh:
            fh.writelines(lines)
