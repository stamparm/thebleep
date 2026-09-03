from thebleep.specific.archlinux import HELPERS
from thebleep.specific.sudo import sudo_support
from thebleep.utils import (command_word_index, for_app,
                            replace_argument_prefix, which)


INVALID_OPTIONS = "surqfdvt"


def _invalid_option(command):
    start = command_word_index(command.script_parts)
    return next((part[1]
                 for part in command.script_parts[start + 1:]
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


# On wherever pacman is. This used to take `archlinux_env()`'s answer, which is
# "is pkgfile installed" -- the question the *package-for-a-command* rule has
# to ask, and one a stock Arch answers no to. Fixing a lower-case `-s` needs
# nothing but pacman itself, so `pacman -s vim` got no correction on most of
# the machines that have pacman.
enabled_by_default = any(which(name) for name in ('pacman',) + HELPERS)
