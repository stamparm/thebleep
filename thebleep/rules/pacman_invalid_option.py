from thebleep.specific.archlinux import archlinux_env
from thebleep.specific.sudo import sudo_support
from thebleep.utils import for_app
import re


@sudo_support
@for_app("pacman")
def match(command):
    return command.output.startswith("error: invalid option '-") and any(
        " -{}".format(option) in command.script for option in "surqfdvt"
    )


def get_new_command(command):
    option = re.findall(r" -[dfqrstuv]", command.script)[0]
    return re.sub(option, option.upper(), command.script)


# The pair, not the tuple: `archlinux_env()` answers with (enabled, helper), and
# a two-element tuple is truthy, so this rule was on everywhere -- including
# machines with no `pacman` at all, where its own `@for_app` was the only thing
# stopping it.
enabled_by_default, _ = archlinux_env()
