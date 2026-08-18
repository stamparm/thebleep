# -*- encoding: utf-8 -*-

import pytest
from itertools import islice
from thebleep import ui
from thebleep.types import CorrectedCommand
from thebleep import const


@pytest.fixture
def patch_get_key(monkeypatch):
    def patch(vals):
        vals = iter(vals)
        monkeypatch.setattr('thebleep.ui.get_key', lambda: next(vals))

    return patch


def test_read_actions(patch_get_key):
    patch_get_key([
        # Enter:
        '\n',
        # Enter:
        '\r',
        # Ignored:
        'x', 'y',
        # Up:
        const.KEY_UP, 'k',
        # Down:
        const.KEY_DOWN, 'j',
        # Ctrl+C:
        const.KEY_CTRL_C, 'q',
        # Escape:
        const.KEY_ESCAPE])
    assert (list(islice(ui.read_actions(), 9))
            == [const.ACTION_SELECT, const.ACTION_SELECT,
                const.ACTION_PREVIOUS, const.ACTION_PREVIOUS,
                const.ACTION_NEXT, const.ACTION_NEXT,
                const.ACTION_ABORT, const.ACTION_ABORT,
                const.ACTION_ABORT])


def test_command_selector():
    selector = ui.CommandSelector(iter([1, 2, 3]))
    assert selector.value == 1
    selector.next()
    assert selector.value == 2
    selector.next()
    assert selector.value == 3
    selector.next()
    assert selector.value == 1
    selector.previous()
    assert selector.value == 3


@pytest.mark.usefixtures('no_colors')
class TestSelectCommand(object):
    @pytest.fixture(autouse=True)
    def is_interactive(self, mocker):
        return mocker.patch('thebleep.ui.is_interactive', return_value=True)

    @pytest.fixture
    def commands_with_side_effect(self):
        return [CorrectedCommand('ls', lambda *_: None, 100),
                CorrectedCommand('cd', lambda *_: None, 100)]

    @pytest.fixture
    def commands(self):
        return [CorrectedCommand('ls', None, 100),
                CorrectedCommand('cd', None, 100)]

    def test_without_commands(self, capsys):
        assert ui.select_command(iter([])) is None
        assert capsys.readouterr() == ('', 'No bleeps given\n')

    def test_without_confirmation(self, capsys, commands, settings):
        settings.require_confirmation = False
        assert ui.select_command(iter(commands)) == commands[0]
        assert capsys.readouterr() == ('', const.USER_COMMAND_MARK + 'ls\n')

    def test_without_confirmation_with_side_effects(
            self, capsys, commands_with_side_effect, settings):
        settings.require_confirmation = False
        assert (ui.select_command(iter(commands_with_side_effect))
                == commands_with_side_effect[0])
        assert capsys.readouterr() == ('', const.USER_COMMAND_MARK + 'ls (+side effect)\n')

    def test_with_confirmation(self, capsys, patch_get_key, commands):
        patch_get_key(['\n'])
        assert ui.select_command(iter(commands)) == commands[0]
        assert capsys.readouterr() == (
            '', const.USER_COMMAND_MARK + u'\x1b[1K\rls [enter/↑/↓/ctrl+c/esc]\n')

    def test_with_confirmation_abort(self, capsys, patch_get_key, commands):
        patch_get_key([const.KEY_CTRL_C])
        assert ui.select_command(iter(commands)) is None
        assert capsys.readouterr() == (
            '', const.USER_COMMAND_MARK + u'\x1b[1K\rls [enter/↑/↓/ctrl+c/esc]\nAborted\n')

    def test_with_confirmation_abort_with_escape(self, capsys, patch_get_key,
                                                 commands):
        patch_get_key([const.KEY_ESCAPE])
        assert ui.select_command(iter(commands)) is None
        assert capsys.readouterr() == (
            '', const.USER_COMMAND_MARK + u'\x1b[1K\rls [enter/↑/↓/ctrl+c/esc]\nAborted\n')

    def test_with_confirmation_with_side_effct(self, capsys, patch_get_key,
                                               commands_with_side_effect):
        patch_get_key(['\n'])
        assert (ui.select_command(iter(commands_with_side_effect))
                == commands_with_side_effect[0])
        assert capsys.readouterr() == (
            '', const.USER_COMMAND_MARK + u'\x1b[1K\rls (+side effect) [enter/↑/↓/ctrl+c/esc]\n')

    def test_without_tty(self, capsys, commands, is_interactive):
        is_interactive.return_value = False
        assert ui.select_command(iter(commands)) is None
        assert capsys.readouterr() == (
            '', const.USER_COMMAND_MARK + 'ls\n'
            'Aborted: no terminal to confirm on, rerun with --yes\n')

    def test_without_tty_and_confirmation(self, capsys, commands, settings,
                                          is_interactive):
        is_interactive.return_value = False
        settings.require_confirmation = False
        assert ui.select_command(iter(commands)) == commands[0]
        assert capsys.readouterr() == ('', const.USER_COMMAND_MARK + 'ls\n')

    def test_with_confirmation_select_second(self, capsys, patch_get_key, commands):
        patch_get_key([const.KEY_DOWN, '\n'])
        assert ui.select_command(iter(commands)) == commands[1]
        stderr = (
            u'{mark}\x1b[1K\rls [enter/↑/↓/ctrl+c/esc]'
            u'{mark}\x1b[1K\rcd [enter/↑/↓/ctrl+c/esc]\n'
        ).format(mark=const.USER_COMMAND_MARK)
        assert capsys.readouterr() == ('', stderr)
