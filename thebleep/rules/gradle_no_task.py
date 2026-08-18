import re
from subprocess import Popen, PIPE
from thebleep.utils import for_app, eager, replace_command

regex = re.compile(r"Task '(.*)' (is ambiguous|not found)")

# The title gradle prints between two rules above the list, which is not a
# task: "Tasks runnable from root project 'x'", "All tasks runnable from ..."
# with `--all`, or "... from project ':sub'" in a subproject.
TITLE = re.compile(r"(All t|T)asks runnable from ")


@for_app('gradle', 'gradlew')
def match(command):
    return regex.findall(command.output)


@eager
def _get_all_tasks(gradle):
    proc = Popen([gradle, 'tasks'], stdout=PIPE)
    should_yield = False
    for line in proc.stdout.readlines():
        line = line.decode().strip()
        if line.startswith('----'):
            should_yield = True
            continue

        if not line.strip():
            should_yield = False
            continue

        if should_yield and not TITLE.match(line):
            yield line.split(' ')[0]


def get_new_command(command):
    wrong_task = regex.findall(command.output)[0][0]
    all_tasks = _get_all_tasks(command.script_parts[0])
    return replace_command(command, wrong_task, all_tasks)
