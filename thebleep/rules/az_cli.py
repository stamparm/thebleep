import re

from thebleep.utils import for_app, replace_argument

# What `az` says when a word of the command itself is not one it knows, and the
# recommendation it prints under it. Both come from azure-cli's own parser,
# which took this message over from knack and worded it differently.
MISSPELLED = re.compile(r"'([^']+)' is misspelled or not recognized by "
                        r"the system")
DID_YOU_MEAN = re.compile(r"Did you mean '([^']+)' \?")

# knack's wording, for an `az` old enough to still be using it.
NOT_IN_COMMAND_GROUP = re.compile(r"'([^']+)' is not in the '[^']*' "
                                  r"command group")
MOST_SIMILAR = re.compile(r"^The most similar choices? to '[^']*'(?: is)?:\n"
                          r"\s*(.*)$", re.MULTILINE)


def _mistake_and_options(output):
    """The word `az` did not recognise, and what it suggests instead."""
    misspelled = MISSPELLED.search(output)
    if misspelled:
        return misspelled.group(1), DID_YOU_MEAN.findall(output)

    not_in_group = NOT_IN_COMMAND_GROUP.search(output)
    if not_in_group:
        return not_in_group.group(1), MOST_SIMILAR.findall(output)

    return None, []


@for_app('az')
def match(command):
    mistake, options = _mistake_and_options(command.output)
    return bool(mistake and options)


def get_new_command(command):
    mistake, options = _mistake_and_options(command.output)
    return [replace_argument(command.script, mistake, o) for o in options]
