# -*- encoding: utf-8 -*-

"""`winget isntall vim` -> `winget install vim`.

winget answers a command it does not know with its whole usage text, and that
text lists the commands it does know, one per indented line under

    The following commands are available:

So the answer is already on the screen and nothing has to be run to get it:
the word after `winget` is matched against that list.

"""

import re
from thebleep.utils import (command_word_index, for_app, replace_command,
                            which)

enabled_by_default = bool(which('winget'))

AVAILABLE = 'The following commands are available'
COMMAND_LINE = re.compile(r'^ {2,}([a-z][a-z0-9-]*) {2,}\S', re.MULTILINE)


def _typed(command):
    start = command_word_index(command.script_parts)
    for part in command.script_parts[start + 1:]:
        if not part.startswith('-'):
            return part
    return None


def _listed(output):
    if AVAILABLE not in output:
        return []
    return COMMAND_LINE.findall(output[output.index(AVAILABLE):])


@for_app('winget')
def match(command):
    typed = _typed(command)
    listed = _listed(command.output)
    return bool(typed and listed and typed not in listed)


def get_new_command(command):
    return replace_command(command, _typed(command), _listed(command.output))
