# -*- encoding: utf-8 -*-

import pytest

from thebleep.rules import switch_lang
from thebleep.types import Command


@pytest.mark.parametrize('command', [
    Command(u'фзе-пуе', 'command not found: фзе-пуе'),
    Command(u'λσ', 'command not found: λσ'),
    Command(u'שפא-עקא', 'command not found: שפא-עקא'),
    Command(u'ךד', 'command not found: ךד'),
    Command(u'녀애 ㅣㄴ', 'command not found: 녀애 ㅣㄴ')])
def test_match(command):
    assert switch_lang.match(command)


@pytest.mark.parametrize('command', [
    Command(u'pat-get', 'command not found: pat-get'),
    Command(u'ls', 'command not found: ls'),
    Command(u'идууз', 'command not found: идууз'),
    Command(u'фзе-пуе', 'some info'),
    Command(u'שפא-עקא', 'some info'),
    Command(u'녀애 ㅣㄴ', 'some info')])
def test_not_match(command):
    assert not switch_lang.match(command)


@pytest.mark.parametrize('command, new_command', [
    (Command(u'фзе-пуе штыефдд мшь', ''), 'apt-get install vim'),
    (Command(u'λσ -λα', ''), 'ls -la'),
    (Command(u'שפא-עקא ןמדאשךך הןצ', ''), 'apt-get install vim'),
    (Command(u'ךד -ךש', ''), 'ls -la'),
    (Command(u'멧-ㅎㄷㅅ ㅑㅜㄴㅅ미ㅣ 퍄ㅡ', ''), 'apt-get install vim'),
    (Command(u'ㅣㄴ -ㅣㅁ', ''), 'ls -la'),
    (Command(u'ㅔㅁㅅ촤', ''), 'patchk'), ])
def test_get_new_command(command, new_command):
    assert switch_lang.get_new_command(command) == new_command


def test_it_does_not_change_the_command_other_rules_are_looking_at():
    """`command` is shared across every rule in one correction.

    This assigned to `command.script` to hold its decomposed Korean, so every
    rule consulted after it saw a command the user had not typed. `man.py` has a
    comment about avoiding exactly this.

    """
    from thebleep.rules import switch_lang

    command = Command(u'ㅣㄴ', 'command not found')
    before = command.script
    switch_lang.get_new_command(command)
    assert command.script == before


def test_a_layout_it_cannot_place_is_not_a_crash():
    """`_switch_command(command, None)` indexes into the layout.

    Reachable because `match` lets a Korean script through without finding a
    layout for it, so `get_new_command` could be called with no layout to use.

    """
    from thebleep.rules import switch_lang

    command = Command(u'ㅣㄴ mixed with latin', 'command not found')
    assert switch_lang.get_new_command(command) is not None
