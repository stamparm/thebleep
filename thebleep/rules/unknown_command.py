import re
from thebleep.utils import replace_command


# Anchored to a line: an unanchored `[^:]*` can swallow the whole output and
# then backtrack a character at a time, which on the megabyte a failed build
# prints takes longer than anyone will wait.
BROKEN = re.compile(r"^([^:\n]*): Unknown command", re.MULTILINE)


def match(command):
    return (BROKEN.search(command.output) is not None
            and re.search(r"Did you mean ([^?]*)?", command.output) is not None)


def get_new_command(command):
    broken_cmd = BROKEN.findall(command.output)[0]
    matched = re.findall(r"Did you mean ([^?]*)?", command.output)
    return replace_command(command, broken_cmd, matched)
