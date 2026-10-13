import re
from thebleep.utils import (command_word_index, for_app, quote_words,
                            replace_argument)


@for_app('yarn', at_least=1)
def match(command):
    return 'Did you mean' in command.output


def get_new_command(command):
    parts = command.script_parts
    found = re.findall(r'Did you mean [`"](?:yarn )?([^`"]*)[`"]',
                       command.output)
    if not found or len(parts) <= command_word_index(parts) + 1:
        return []
    # The word yarn names, when it names one: `yarn run buld` says `Command
    # "buld" not found. Did you mean "build"?`, and replacing the word after
    # `yarn` -- `run` -- gave `yarn build buld` as the first answer.
    named = re.search(r'Command "([^"]+)" not found', command.output)
    if named and named.group(1) in parts:
        broken = named.group(1)
    else:
        broken = parts[command_word_index(parts) + 1]
    return replace_argument(command.script, broken, quote_words(found[0]))
