import re
from thebleep.shells import shell
from thebleep.utils import quote_words


# `\S[^\n]*`, not `(.*?)\n`: the lazy match backtracked to nothing when the
# output had no trailing newline, and the suggestion was ` && bin/rspec`.
SUGGESTION_REGEX = r"To resolve this issue, run:\s+(\S[^\n]*)"


def match(command):
    return "Migrations are pending. To resolve this issue, run:" in command.output


def get_new_command(command):
    found = re.search(SUGGESTION_REGEX, command.output)
    if found is None:
        return []
    # A whole command line out of rails' output, repeated word by word.
    return shell.and_(quote_words(found.group(1).strip()), command.script)
