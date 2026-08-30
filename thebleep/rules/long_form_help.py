from thebleep.utils import replace_argument
import re

# regex to match a suggested help command from the tool output
help_regex = r"(?:Run|Try) '([^']+)'(?: or '[^']+')? for (?:details|more information)."


def match(command):
    # An option failure may include `Try 'tool --help'`, but that is advice
    # from the failed tool, not a correction to the command. A specialised
    # option rule gets first chance to produce a real replacement; if it has
    # no evidence, abstain instead of offering a help screen as the answer.
    if re.search(r'(?:unrecognized|unknown|invalid) option',
                 command.output, re.I) is not None:
        return False

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
