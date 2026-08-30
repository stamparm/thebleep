import re
from thebleep.shells import shell
from thebleep.utils import (for_app, eager, get_closest, cache,
                            replace_argument_prefix, tool_lines)

regex = re.compile(r'Warning: Task "(.*)" not found.')


@for_app('grunt')
def match(command):
    return regex.findall(command.output)


@cache('Gruntfile.js')
@eager
def _get_all_tasks():
    should_yield = False
    for line in tool_lines(['grunt', '--help']):
        line = line.strip()

        if 'Available tasks' in line:
            should_yield = True
            continue

        if should_yield and not line:
            return

        if '  ' in line:
            yield line.split(' ')[0]


def get_new_command(command):
    misspelled_task = regex.findall(command.output)[0].split(':')[0]
    tasks = _get_all_tasks()
    # The task name is quoted: it is a key in the repository's Gruntfile, so
    # it can be any string at all, and the result goes back to the shell.
    fixed = get_closest(misspelled_task, tasks, fallback_to_first=False)
    if fixed is None:
        return command.script
    return replace_argument_prefix(command.script, misspelled_task,
                                   shell.quote(fixed))
