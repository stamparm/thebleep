import re
from thebleep.utils import get_closest, for_app


def extract_possibilities(command):
    possib = re.findall(r'\n\(did you mean one of ([^\?]+)\?\)', command.output)
    if possib:
        return possib[0].split(', ')
    possib = re.findall(r'\n    ([^$]+)$', command.output)
    if possib:
        return possib[0].split(' ')
    return possib


@for_app('hg')
def match(command):
    return ('hg: unknown command' in command.output
            and '(did you mean one of ' in command.output
            or "hg: command '" in command.output
            and "' is ambiguous:" in command.output)


def get_new_command(command):
    script = command.script_parts[:]
    if len(script) < 2:
        return []

    possibilities = extract_possibilities(command)
    closest = get_closest(script[1], possibilities)
    if closest is None:
        # `' '.join` on a `None` is a `TypeError`, which is a rule that never
        # fires rather than one that stands aside.
        return []

    script[1] = closest
    return ' '.join(script)
