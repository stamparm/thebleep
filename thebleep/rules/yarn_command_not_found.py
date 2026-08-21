import re
from thebleep.utils import (for_app, eager, replace_command, replace_argument,
                            cache, which, tool_lines)
from thebleep.shells import shell
from thebleep import matching

regex = re.compile(r'error Command "(.*)" not found.')


@for_app('yarn')
def match(command):
    return regex.findall(command.output)


npm_commands = {'require': 'add'}


@eager
def _get_all_tasks():
    should_yield = False
    for line in tool_lines(['yarn', '--help']):
        line = line.strip()

        if 'Commands:' in line:
            should_yield = True
            continue

        if should_yield and '- ' in line:
            yield line.split(' ')[-1]


if which('yarn'):
    _get_all_tasks = cache(which('yarn'))(_get_all_tasks)


def get_new_command(command):
    misspelled_task = regex.findall(command.output)[0]
    if misspelled_task in npm_commands:
        yarn_command = npm_commands[misspelled_task]
        return replace_argument(command.script, misspelled_task,
                                 shell.quote(yarn_command))
    else:
        tasks = _get_all_tasks()
        if not tasks:
            return []
        # Use thebleep.matching.order() for proper typo detection
        ordered = matching.order(misspelled_task, tasks, limit=3)
        if not ordered:
            return []
        return replace_command(command, misspelled_task, ordered)
