import re
from thebleep.utils import replace_command, for_app, cache, tool_lines


@for_app('gulp')
def match(command):
    return 'is not in your gulpfile' in command.output


@cache('gulpfile.js')
def get_gulp_tasks():
    return tool_lines(['gulp', '--tasks-simple'])


def get_new_command(command):
    # `[^']+`, not `\w+`: gulp tasks are `build-css` and `build:css` as often
    # as not, and `\w+` could not match them.
    found = re.findall(r"Task '([^']+)' is not in your gulpfile",
                       command.output)
    if not found:
        return []
    return replace_command(command, found[0], get_gulp_tasks())
