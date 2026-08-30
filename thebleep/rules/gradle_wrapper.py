import os
from thebleep.utils import for_app, which


@for_app('gradle')
def match(command):
    return (not which(command.script_parts[0])
            and 'not found' in command.output
            and os.path.isfile('gradlew'))


def get_new_command(command):
    parts = command.script.split(None, 1)
    return u'./gradlew' if len(parts) == 1 \
        else u'./gradlew {}'.format(parts[1])
