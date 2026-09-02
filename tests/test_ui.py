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
        const.KEY_ESCAPE,
        # Tab:
        const.KEY_TAB])
    assert (list(islice(ui.read_actions(), 10))
            == [const.ACTION_SELECT, const.ACTION_SELECT,
                const.ACTION_PREVIOUS, const.ACTION_PREVIOUS,
                const.ACTION_NEXT, const.ACTION_NEXT,
                const.ACTION_ABORT, const.ACTION_ABORT,
                const.ACTION_ABORT, const.ACTION_EDIT])


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

    @pytest.fixture(autouse=True)
    def a_terminal_that_renders_escapes(self, mocker):
        """Which is what `\x1b[1K` -- erase the line -- needs to be worth
        writing.

        It used to be hard-coded, so it went out whether or not anything would
        render it: `no_colors`, a pipe, a log file. It goes through `color` now,
        like every other escape code here, and `color` asks `sys.stderr`. Under
        `capsys` the answer is no, so the terminal is stood in for.

        """
        from thebleep import logs

        mocker.patch.object(logs._ansi_supported, 'cached', True)

    @pytest.fixture
    def commands_with_side_effect(self):
        return [CorrectedCommand('ls', lambda *_: None, 100),
                CorrectedCommand('cd', lambda *_: None, 100)]

    @pytest.fixture
    def commands(self):
        return [CorrectedCommand('ls', None, 100),
                CorrectedCommand('cd', None, 100)]

    def test_without_commands(self, capsys):
        assert ui.select_command(iter([])) == (None, const.ACTION_ABORT)
        assert capsys.readouterr() == ('', 'No bleeps given\n')

    def test_without_confirmation(self, capsys, commands, settings):
        settings.require_confirmation = False
        assert ui.select_command(iter(commands)) == (commands[0],
                                                     const.ACTION_SELECT)
        assert capsys.readouterr() == ('', const.USER_COMMAND_MARK + 'ls\n')

    def test_without_confirmation_with_side_effects(
            self, capsys, commands_with_side_effect, settings):
        settings.require_confirmation = False
        assert (ui.select_command(iter(commands_with_side_effect))
                == (commands_with_side_effect[0], const.ACTION_SELECT))
        assert capsys.readouterr() == ('', const.USER_COMMAND_MARK + 'ls (+side effect)\n')

    @pytest.fixture
    def trusted_commands(self):
        from thebleep.types import Rule

        read = Rule('read_it', lambda _: True, lambda _: 'ls', True, None,
                    1000, True)
        return [CorrectedCommand('ls', None, 100, rule=read),
                CorrectedCommand('cd', None, 100, rule=read)]

    @pytest.fixture
    def failed(self):
        from thebleep.types import Command

        return Command('sl', 'sl: command not found')

    def test_trusted_enough_runs_unasked(
            self, capsys, trusted_commands, settings, failed):
        """No key is read: the first suggestion runs, and the line under it
        says what let it through."""
        settings.auto_run_confidence = 0.9
        assert ui.select_command(iter(trusted_commands), failed) == (
            trusted_commands[0], const.ACTION_SELECT)
        out, err = capsys.readouterr()
        assert out == ''
        assert err.startswith(const.USER_COMMAND_MARK + 'ls\n')
        assert 'ran without asking: 95% confidence' in err

    def test_not_trusted_enough_asks(self, capsys, patch_get_key, commands,
                                     settings, failed):
        """A guess from the command alone scores 0.75, under the threshold,
        so the prompt appears and enter is what runs it."""
        settings.auto_run_confidence = 0.9
        patch_get_key(['\n'])
        assert ui.select_command(iter(commands), failed) == (
            commands[0], const.ACTION_SELECT)
        err = capsys.readouterr()[1]
        assert 'enter' in err
        assert 'ran without asking' not in err

    def test_trust_never_skips_a_side_effect(self, capsys, patch_get_key,
                                             commands_with_side_effect,
                                             settings, failed):
        settings.auto_run_confidence = 0.1
        patch_get_key(['\n'])
        assert ui.select_command(iter(commands_with_side_effect), failed) == (
            commands_with_side_effect[0], const.ACTION_SELECT)
        assert 'ran without asking' not in capsys.readouterr()[1]

    def test_trust_goes_to_the_editor_when_that_is_all_there_is(
            self, capsys, trusted_commands, settings, failed, mocker):
        """Nushell cannot run a string, so trust means the correction is
        placed on the line unasked -- nothing runs either way."""
        settings.auto_run_confidence = 0.9
        mocker.patch('thebleep.shells.shell.can_run_corrections',
                     return_value=False)
        assert ui.select_command(iter(trusted_commands), failed) == (
            trusted_commands[0], const.ACTION_EDIT)

    def test_with_confirmation(self, capsys, patch_get_key, commands):
        patch_get_key(['\n'])
        assert ui.select_command(iter(commands)) == (commands[0],
                                                     const.ACTION_SELECT)
        assert capsys.readouterr() == (
            '', u'\x1b[1K\r' + const.USER_COMMAND_MARK
            + u'❯ ls\n[enter/↑/↓/?/ctrl+c/esc]\n')

    def test_with_confirmation_abort(self, capsys, patch_get_key, commands):
        patch_get_key([const.KEY_CTRL_C])
        assert ui.select_command(iter(commands)) == (None, const.ACTION_ABORT)
        assert capsys.readouterr() == (
            '', u'\x1b[1K\r' + const.USER_COMMAND_MARK
            + u'❯ ls\n[enter/↑/↓/?/ctrl+c/esc]\nAborted\n')

    def test_with_confirmation_abort_with_escape(self, capsys, patch_get_key,
                                                 commands):
        patch_get_key([const.KEY_ESCAPE])
        assert ui.select_command(iter(commands)) == (None, const.ACTION_ABORT)
        assert capsys.readouterr() == (
            '', u'\x1b[1K\r' + const.USER_COMMAND_MARK
            + u'❯ ls\n[enter/↑/↓/?/ctrl+c/esc]\nAborted\n')

    def test_with_confirmation_with_side_effct(self, capsys, patch_get_key,
                                               commands_with_side_effect):
        patch_get_key(['\n'])
        assert (ui.select_command(iter(commands_with_side_effect))
                == (commands_with_side_effect[0], const.ACTION_SELECT))
        assert capsys.readouterr() == (
            '', u'\x1b[1K\r' + const.USER_COMMAND_MARK
            + u'❯ ls (+side effect)\n[enter/↑/↓/?/ctrl+c/esc]\n')

    def test_without_tty(self, capsys, commands, is_interactive):
        is_interactive.return_value = False
        assert ui.select_command(iter(commands)) == (None, const.ACTION_ABORT)
        assert capsys.readouterr() == (
            '', const.USER_COMMAND_MARK + 'ls\n'
            'Aborted: no terminal to confirm on, rerun with --yes\n')

    def test_without_tty_and_confirmation(self, capsys, commands, settings,
                                          is_interactive):
        is_interactive.return_value = False
        settings.require_confirmation = False
        assert ui.select_command(iter(commands)) == (commands[0],
                                                     const.ACTION_SELECT)
        assert capsys.readouterr() == ('', const.USER_COMMAND_MARK + 'ls\n')

    def test_with_confirmation_select_second(self, capsys, patch_get_key, commands):
        patch_get_key([const.KEY_DOWN, '\n'])
        assert ui.select_command(iter(commands)) == (commands[1],
                                                     const.ACTION_SELECT)
        stderr = (
            u'\x1b[1K\r{mark}❯ ls\n[enter/↑/↓/?/ctrl+c/esc]'
            # Back over the two lines drawn, clear, and draw the list with
            # the second row chosen and a position in the hint.
            u'\r\x1b[1A\x1b[J{mark}  ls\n❯ cd\n[enter/↑/↓/?/ctrl+c/esc]  2/2\n'
        ).format(mark=const.USER_COMMAND_MARK)
        assert capsys.readouterr() == ('', stderr)

    def test_a_console_without_escapes_gets_one_line(
            self, capsys, mocker, patch_get_key, commands):
        """Nothing can move the cursor back, so the list cannot be redrawn;
        the one-line prompt is what such a console had before and keeps."""
        from thebleep import logs

        mocker.patch.object(logs._ansi_supported, 'cached', False)
        patch_get_key([const.KEY_DOWN, '\n'])
        assert ui.select_command(iter(commands)) == (commands[1],
                                                     const.ACTION_SELECT)
        assert capsys.readouterr() == (
            '', u'{mark}\rls [enter/↑/↓/?/ctrl+c/esc]'
                u'{mark}\rcd [enter/↑/↓/?/ctrl+c/esc]\n'.format(
                    mark=const.USER_COMMAND_MARK))


@pytest.mark.usefixtures('no_colors')
class TestEdit(object):
    """Handing a correction back to be edited instead of run."""

    @pytest.fixture(autouse=True)
    def is_interactive(self, mocker):
        return mocker.patch('thebleep.ui.is_interactive', return_value=True)

    @pytest.fixture
    def commands(self):
        return [CorrectedCommand('ls', None, 100),
                CorrectedCommand('cd', None, 100)]

    @pytest.fixture
    def can_edit(self, os_environ):
        os_environ['TB_CAN_EDIT'] = '1'

    def test_tab_asks_to_edit(self, patch_get_key, commands, can_edit):
        patch_get_key([const.KEY_TAB])
        assert ui.select_command(iter(commands)) == (commands[0],
                                                     const.ACTION_EDIT)

    def test_tab_edits_the_one_on_screen(self, patch_get_key, commands,
                                         can_edit):
        patch_get_key([const.KEY_DOWN, const.KEY_TAB])
        assert ui.select_command(iter(commands)) == (commands[1],
                                                     const.ACTION_EDIT)

    def test_editing_is_offered_when_the_shell_can(self, capsys, patch_get_key,
                                                   commands, can_edit):
        patch_get_key(['\n'])
        ui.select_command(iter(commands))
        assert u'tab=edit' in capsys.readouterr()[1]

    def test_editing_is_not_offered_when_it_cannot(self, capsys, patch_get_key,
                                                   commands):
        patch_get_key(['\n'])
        ui.select_command(iter(commands))
        assert u'tab=edit' not in capsys.readouterr()[1]

    def test_tab_does_nothing_when_unsupported(self, patch_get_key, commands):
        """Nothing was offered, so nothing is promised -- and nothing runs."""
        patch_get_key([const.KEY_TAB, '\n'])
        assert ui.select_command(iter(commands)) == (commands[0],
                                                     const.ACTION_SELECT)

    def test_edit_flag_skips_the_question(self, commands, settings, can_edit):
        settings.edit = True
        settings.require_confirmation = False
        assert ui.select_command(iter(commands)) == (commands[0],
                                                     const.ACTION_EDIT)

    def test_edit_flag_still_asks_which(self, patch_get_key, commands,
                                        settings, can_edit):
        settings.edit = True
        patch_get_key([const.KEY_DOWN, '\n'])
        assert ui.select_command(iter(commands)) == (commands[1],
                                                     const.ACTION_EDIT)

    def test_edit_flag_without_support_refuses(self, capsys, commands,
                                               settings):
        """Better to do nothing than to run what was only meant to be edited."""
        settings.edit = True
        assert ui.select_command(iter(commands)) == (None, const.ACTION_ABORT)
        assert 'cannot put a command in the line editor' in capsys.readouterr()[1]


class TestTheHistoryKeys(object):
    """Ctrl+P and Ctrl+N, which were bound the wrong way round.

    The letter keys follow the colemak argument in `const` -- `n` sits where a
    qwerty `j` does -- but Ctrl+P and Ctrl+N are not a layout argument. They are
    the readline bindings every shell's own history uses, and there Ctrl+P is
    previous and Ctrl+N is next.

    """

    def test_ctrl_p_goes_back(self, mocker):
        mocker.patch('thebleep.ui.get_key',
                     side_effect=[const.KEY_CTRL_P, const.KEY_CTRL_C])
        assert next(ui.read_actions()) == const.ACTION_PREVIOUS

    def test_ctrl_n_goes_forward(self, mocker):
        mocker.patch('thebleep.ui.get_key',
                     side_effect=[const.KEY_CTRL_N, const.KEY_CTRL_C])
        assert next(ui.read_actions()) == const.ACTION_NEXT
