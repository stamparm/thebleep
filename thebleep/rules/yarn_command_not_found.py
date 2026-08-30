import re
from thebleep import project_context
from thebleep.utils import (for_app, eager, replace_command, replace_argument,
                            cache, which, tool_lines)

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
        return replace_argument(command.script, misspelled_task, yarn_command)
    else:
        tasks = _get_all_tasks()
        project_scripts = project_context.package_scripts()
        if project_scripts is not None:
            tasks = project_scripts + [task for task in tasks
                                       if task not in project_scripts]
        return replace_command(command, misspelled_task, tasks)
