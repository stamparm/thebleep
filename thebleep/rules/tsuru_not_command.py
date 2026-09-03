import re
from thebleep.utils import get_all_matched_commands, replace_command, for_app


@for_app('tsuru')
def match(command):
    return (' is not a tsuru command. See "tsuru help".' in command.output
            and '\nDid you mean?\n\t' in command.output)


def get_new_command(command):
    found = re.findall(r'tsuru: "([^"]*)" is not a tsuru command',
                       command.output)
    if not found:
        return []
    return replace_command(command, found[0],
                           get_all_matched_commands(command.output))
