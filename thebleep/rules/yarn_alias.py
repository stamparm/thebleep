import re
from thebleep.utils import (command_word_index, for_app, quote_words,
                            replace_argument)


@for_app('yarn', at_least=1)
def match(command):
    return 'Did you mean' in command.output


def get_new_command(command):
    parts = command.script_parts
    broken = parts[command_word_index(parts) + 1]
    fix = re.findall(r'Did you mean [`"](?:yarn )?([^`"]*)[`"]', command.output)[0]

    return replace_argument(command.script, broken, quote_words(fix))
