import re
from thebleep.shells import shell
from thebleep.utils import get_closest, for_app, raw_script_parts


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
    parsed = command.script_parts
    script = raw_script_parts(command.script)
    if len(parsed) < 2 or len(script) != len(parsed):
        return []

    possibilities = extract_possibilities(command)
    closest = get_closest(parsed[1], possibilities)
    if closest is None:
        # `' '.join` on a `None` is a `TypeError`, which is a rule that never
        # fires rather than one that stands aside.
        return []

    script[1] = shell.quote(closest)
    return ' '.join(script)
