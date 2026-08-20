import re
from thebleep.utils import replace_command, for_app


AMBIGUOUS = re.compile(r"ambiguous command: (.*), could be: (.*)")


@for_app('tmux')
def match(command):
    # Both substrings on the *same line*, which is what the regex below needs
    # and what the two `in` tests did not check -- so a message with them on
    # separate lines got as far as `None.group(1)`.
    return AMBIGUOUS.search(command.output) is not None


def get_new_command(command):
    cmd = AMBIGUOUS.search(command.output)
    if not cmd:
        return []

    old_cmd = cmd.group(1)
    suggestions = [c.strip() for c in cmd.group(2).split(',')]

    return replace_command(command, old_cmd, suggestions)
