# -*- encoding: utf-8 -*-

"""`task buld` -> `task build` from Task's hint or Taskfile.yml."""

import re

from thebleep import matching, project_context
from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument_in_command


MISSING = re.compile(r'Task "([^"\r\n]+)" does not exist')
SUGGESTED = re.compile(r'Did you mean "([^"\r\n]+)"')


@for_app('task')
def match(command):
    return MISSING.search(command.output) is not None


def get_new_command(command):
    broken = MISSING.search(command.output).group(1)
    suggested = SUGGESTED.findall(command.output)
    candidates = matching.order(broken, suggested, limit=3)
    tasks = project_context.task_names()
    if tasks is not None:
        candidates += [name for name in matching.rank(broken, tasks, limit=3)
                       if name not in candidates]

    return [
        replace_argument_in_command(command, 'task', broken,
                                    shell.quote(candidate))
        for candidate in candidates]
