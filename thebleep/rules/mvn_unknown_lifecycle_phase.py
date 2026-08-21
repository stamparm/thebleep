from thebleep.utils import for_app, replace_command
from thebleep.shells import shell
from thebleep import matching
import re


def _get_failed_lifecycle(command):
    return re.search(r'\[ERROR\] Unknown lifecycle phase "(.+)"',
                     command.output)


def _getavailable_lifecycles(command):
    return re.search(
        r'Available lifecycle phases are: (.+) -> \[Help 1\]', command.output)


@for_app('mvn')
def match(command):
    failed_lifecycle = _get_failed_lifecycle(command)
    available_lifecycles = _getavailable_lifecycles(command)
    return available_lifecycles and failed_lifecycle


def get_new_command(command):
    failed_lifecycle = _get_failed_lifecycle(command)
    available_lifecycles = _getavailable_lifecycles(command)
    if available_lifecycles and failed_lifecycle:
        available = available_lifecycles.group(1).split(", ")
        # Use thebleep.matching.order() for Damerau-Levenshtein distance
        ordered = matching.order(failed_lifecycle.group(1), available, limit=3)
        if not ordered:
            return []
        # replace_command handles quoting internally
        return replace_command(command, failed_lifecycle.group(1), ordered)
    else:
        return []
