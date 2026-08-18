import re
from thebleep.utils import replace_argument, for_app


NOT_DEFINED = re.compile(r"Command \"([^']*)\" is not defined")
DID_YOU_MEAN = re.compile(r'Did you mean (?:this|one of these)\?[^\n]*\n\s*([^\n]*)')


def _install_meant_require(command):
    return ('install' in command.script_parts
            and 'composer require' in command.output.lower())


def _misspelled(command):
    """The command composer did not recognise and what it suggests instead."""
    broken = NOT_DEFINED.search(command.output)
    suggested = DID_YOU_MEAN.search(command.output)
    if broken and suggested:
        return broken.group(1), suggested.group(1).strip()
    return None


@for_app('composer')
def match(command):
    # Both halves, not just the "did you mean" line: composer prints the two
    # separately and matching on one of them alone left `get_new_command` to
    # find the other one or raise IndexError.
    return _install_meant_require(command) or _misspelled(command) is not None


def get_new_command(command):
    if _install_meant_require(command):
        broken_cmd, new_cmd = 'install', 'require'
    else:
        broken_cmd, new_cmd = _misspelled(command)
    return replace_argument(command.script, broken_cmd, new_cmd)
