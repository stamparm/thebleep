import re
from thebleep.utils import for_app
from thebleep.specific.brew import brew_available

enabled_by_default = brew_available

# brew says this for anything it is asked to look up by name, and prefixes it
# with `Warning:` for an install and `Error:` for an uninstall, so the prefix is
# left out of it.
NO_FORMULA = re.compile(r'No available formula with the name "[^"]+"\. '
                        r'Did you mean (.+)\?')


def _get_suggestions(str):
    suggestions = str.replace(" or ", ", ").split(", ")
    return suggestions


def _suggested_formulae(output):
    found = NO_FORMULA.search(output)
    return _get_suggestions(found.group(1)) if found else []


@for_app('brew', at_least=2)
def match(command):
    # `command.script`, which this used to look in, holds `install` for
    # `brew uninstall` and `brew reinstall` too -- and correcting either of
    # those to an install would be a wrong and destructive thing to offer.
    return (command.script_parts[1] == 'install'
            and bool(_suggested_formulae(command.output)))


def get_new_command(command):
    return ["brew install " + formula
            for formula in _suggested_formulae(command.output)]
