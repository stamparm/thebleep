import re
from thebleep.shells import shell
from thebleep.utils import quote_words


SUGGESTION_REGEX = r"To resolve this issue, run:\s+(.*?)\n"


def match(command):
    return "Migrations are pending. To resolve this issue, run:" in command.output


def get_new_command(command):
    migration_script = re.search(SUGGESTION_REGEX, command.output).group(1)
    # A whole command line out of rails' output, repeated word by word.
    return shell.and_(quote_words(migration_script), command.script)
