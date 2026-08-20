import re

from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument

INVALID_CHOICE = "(?<=Invalid choice: ')(.*)(?=', maybe you meant:)"
OPTIONS = "^\\s*\\*\\s(.*)"


@for_app('aws')
def match(command):
    # The name has to be *readable*, not just the two marker strings present.
    # They are a weaker test than the lookbehind regex below -- a message with
    # `maybe you meant:` on one line and the choice on another satisfies them
    # and not it -- and then `re.search(...).group(0)` was `None.group(0)`.
    return ("usage:" in command.output
            and "maybe you meant:" in command.output
            and re.search(INVALID_CHOICE, command.output) is not None)


def get_new_command(command):
    found = re.search(INVALID_CHOICE, command.output)
    if not found:
        return []

    mistake = found.group(0)
    options = re.findall(OPTIONS, command.output, flags=re.MULTILINE)
    # Quoted: these come out of the tool's own output, and the result goes
    # back to the shell to be evaluated.
    return [replace_argument(command.script, mistake, shell.quote(o))
            for o in options]
