import re
from thebleep.utils import replace_command, for_app, cache, tool_lines


@for_app('gulp')
def match(command):
    return 'is not in your gulpfile' in command.output


@cache('gulpfile.js')
def get_gulp_tasks():
    return tool_lines(['gulp', '--tasks-simple'])


def get_new_command(command):
    wrong_task = re.findall(r"Task '(\w+)' is not in your gulpfile",
                            command.output)[0]
    return replace_command(command, wrong_task, get_gulp_tasks())
