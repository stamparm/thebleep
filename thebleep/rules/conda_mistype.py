import re
from thebleep.utils import replace_command, for_app


@for_app("conda")
def match(command):
    """
    Match a mistyped command
    """
    return "Did you mean 'conda" in command.output


def get_new_command(command):
    # Two names wanted, and older conda printed only the one it suggested --
    # so `match[1]` was an `IndexError` rather than a rule that stands aside.
    match = re.findall(r"'conda ([^']*)'", command.output)
    if len(match) < 2:
        return []

    broken_cmd = match[0]
    correct_cmd = match[1]
    return replace_command(command, broken_cmd, [correct_cmd])
