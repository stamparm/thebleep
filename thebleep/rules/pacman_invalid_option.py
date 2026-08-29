from thebleep.specific.archlinux import archlinux_env
from thebleep.specific.sudo import sudo_support
from thebleep.utils import for_app, replace_argument_prefix


INVALID_OPTIONS = "surqfdvt"


def _invalid_option(command):
    return next((part[1]
                 for part in command.script_parts[1:]
                 if len(part) > 1 and part.startswith('-')
                 and part[1] in INVALID_OPTIONS), None)


@sudo_support
@for_app("pacman")
def match(command):
    return (command.output.startswith("error: invalid option '-")
            and bool(_invalid_option(command)))


def get_new_command(command):
    option = _invalid_option(command)
    if option is None:
        return command.script

    option = '-{}'.format(option)
    return replace_argument_prefix(command.script, option, option.upper(),
                                   separator='')


# The pair, not the tuple: `archlinux_env()` answers with (enabled, helper), and
# a two-element tuple is truthy, so this rule was on everywhere -- including
# machines with no `pacman` at all, where its own `@for_app` was the only thing
# stopping it.
enabled_by_default, _ = archlinux_env()
