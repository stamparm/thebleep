from thebleep.utils import replace_argument
import re

# regex to match a suggested help command from the tool output
help_regex = r"(?:Run|Try) '([^']+)'(?: or '[^']+')? for (?:details|more information)."


def match(command):
    if re.search(help_regex, command.output, re.I) is not None:
        return True

    if '--help' in command.output:
        return True

    return False


def get_new_command(command):
    # `re.I` here too. `match` searched case-insensitively and this did not, so
    # a program whose wording is `try 'x --help' for more information.` matched
    # and then fell through to `replace_argument` -- which is a no-op on a
    # script with no `-h` in it, and `corrector._worth_offering` then drops a
    # suggestion identical to the command. Silently dead for every lowercase
    # spelling, which is most of them.
    found = re.search(help_regex, command.output, re.I)
    if found is not None:
        return found.group(1)

    return replace_argument(command.script, '-h', '--help')


enabled_by_default = True
priority = 5000
