# -*- encoding: utf-8 -*-

from thebleep.rules.task_no_task import get_new_command, match
from thebleep.types import Command


# Captured from go-task 3.53.1 with a Taskfile task named `build`.
OUTPUT = 'task: Task "buidl" does not exist. Did you mean "build"?'


def test_match_is_limited_to_task():
    assert match(Command('task buidl', OUTPUT))
    assert not match(Command('taskx buidl', OUTPUT))


def test_task_hint_is_suggested_without_a_taskfile(tmpdir, monkeypatch):
    monkeypatch.chdir(tmpdir)

    assert get_new_command(Command('task buidl', OUTPUT)) == ['task build']


def test_declared_task_is_used_when_task_has_no_hint(tmpdir, monkeypatch):
    tmpdir.join('Taskfile.yml').write(
        'tasks:\n'
        '  build:\n'
        '    cmds: []\n'
        '  test:\n'
        '    cmds: []\n')
    monkeypatch.chdir(tmpdir)

    output = 'task: Task "buidl" does not exist'
    assert get_new_command(Command('task buidl', output)) == ['task build']


def test_unreadable_project_metadata_abstains_without_a_hint(tmpdir,
                                                             monkeypatch):
    monkeypatch.chdir(tmpdir)
    assert get_new_command(Command(
        'task buidl', 'task: Task "buidl" does not exist')) == []
