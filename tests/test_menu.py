# -*- encoding: utf-8 -*-

"""The suggestion list: what is drawn, and that it fits."""

import pytest
from thebleep import const, menu
from thebleep.types import Command, CorrectedCommand, Rule


def rule(requires_output=True):
    return Rule('some_rule', lambda _: True, lambda _: 'x', True, None, 1000,
                requires_output)


@pytest.fixture(autouse=True)
def a_terminal(mocker):
    from thebleep import logs

    mocker.patch.object(logs._ansi_supported, 'cached', True)
    mocker.patch.object(menu, 'terminal_width', return_value=80)


class TestChangedWords(object):
    def test_the_new_words_are_the_flagged_ones(self):
        assert menu.changed_words('npm run build', 'cd app && npm run build') \
            == [('cd', True), ('app', True), ('&&', True), ('npm', False),
                ('run', False), ('build', False)]

    def test_a_replaced_word(self):
        assert menu.changed_words('git satus', 'git status') == [
            ('git', False), ('status', True)]

    def test_without_an_original_nothing_is_new(self):
        assert menu.changed_words(None, 'git status') == [
            ('git', False), ('status', False)]


@pytest.mark.usefixtures('no_colors')
class TestRow(object):
    def test_the_chosen_row_is_marked(self):
        command = Command('git satus', 'git: satus is not a git command')
        corrected = CorrectedCommand('git status', None, 1000, rule=rule())
        assert menu.row(corrected, command, True, 80).startswith(u'❯ git status')
        assert menu.row(corrected, command, False, 80).startswith(u'  git status')

    def test_confidence_sits_at_the_right_edge(self):
        command = Command('git satus', 'git: satus is not a git command')
        corrected = CorrectedCommand('git status', None, 1000, rule=rule())
        line = menu.row(corrected, command, True, 60)
        assert line.endswith(u'95%  from what it printed')
        assert len(line) == 60

    def test_the_column_is_dropped_before_the_command_is(self):
        command = Command('git satus', 'git: satus is not a git command')
        corrected = CorrectedCommand('git status', None, 1000, rule=rule())
        line = menu.row(corrected, command, True, 20)
        assert line == u'❯ git status'

    def test_a_long_command_is_cut_to_the_width(self):
        corrected = CorrectedCommand('x' * 200, None, 1000)
        line = menu.row(corrected, None, True, 30)
        assert len(line) == 30
        assert line.endswith(menu.ELLIPSIS)

    def test_a_side_effect_is_said(self):
        corrected = CorrectedCommand('ls', lambda *_: None, 1000)
        assert menu.row(corrected, None, True, 80) == u'❯ ls (+side effect)'

    def test_no_rule_means_no_column(self):
        corrected = CorrectedCommand('ls', None, 1000)
        assert menu.row(corrected, Command('sl', ''), True, 80) == u'❯ ls'

    def test_explicit_evidence_is_the_basis(self):
        corrected = CorrectedCommand('git status', None, 1000, rule=rule(),
                                     confidence=0.98,
                                     evidence=('git named status',))
        line = menu.row(corrected, Command('git satus', 'x'), True, 80)
        assert line.endswith(u'98%  git named status')


def test_colours_mark_what_changed(settings):
    settings.no_colors = False
    corrected = CorrectedCommand('git status', None, 1000)
    line = menu.row(corrected, Command('git satus', None), True, 80)
    assert u'\x1b[1m\x1b[32mstatus\x1b[0m' in line
    assert u'\x1b[1mgit\x1b[0m' in line


class TestWindow(object):
    @pytest.mark.parametrize('index, total, expected', [
        (0, 1, (0, 1)), (0, 3, (0, 3)), (2, 3, (0, 3)),
        (0, 7, (0, 3)), (1, 7, (0, 3)), (2, 7, (1, 4)), (5, 7, (4, 7)),
        (6, 7, (4, 7)),
    ])
    def test_the_chosen_row_stays_on_screen(self, index, total, expected):
        assert menu.window(index, total) == expected


@pytest.mark.usefixtures('no_colors')
class TestKeyHint(object):
    def test_everything_offered(self):
        assert menu.key_hint(True, True, 2, 5) == \
            u'[enter/↑/↓/tab=edit/?/ctrl+c/esc]  2/5'

    def test_one_suggestion_has_no_position(self):
        assert menu.key_hint(False, False, 1, 1) == u'[enter/↑/↓/ctrl+c/esc]'


@pytest.mark.usefixtures('no_colors')
class TestMenu(object):
    def test_the_first_draw_clears_the_line(self, capsys):
        drawn = menu.Menu(False, True)
        drawn.draw([CorrectedCommand('ls', None, 1000)], 0)
        assert capsys.readouterr()[1] == (
            u'\x1b[1K\r' + const.USER_COMMAND_MARK
            + u'❯ ls\n[enter/↑/↓/?/ctrl+c/esc]')

    def test_a_redraw_goes_back_over_what_was_drawn(self, capsys):
        drawn = menu.Menu(False, True)
        commands = [CorrectedCommand(name, None, 1000)
                    for name in ('a', 'b', 'c', 'd')]
        drawn.draw(commands[:1], 0)
        capsys.readouterr()
        drawn.draw(commands, 3)
        assert capsys.readouterr()[1] == (
            u'\r\x1b[1A\x1b[J' + const.USER_COMMAND_MARK
            + u'  b\n  c\n❯ d\n[enter/↑/↓/?/ctrl+c/esc]  4/4')
        drawn.draw(commands, 0)
        assert capsys.readouterr()[1].startswith(u'\r\x1b[3A\x1b[J')


class TestAbstained(object):
    def test_nothing_counted_says_nothing(self):
        assert menu.abstained({}) is None
        assert menu.abstained(None) is None
        assert menu.abstained({'rules': 0}) is None

    def test_the_count(self):
        assert menu.abstained({'rules': 12, 'unread': 0}) == \
            '12 rules for this command; none matched'

    def test_the_unread_output(self):
        assert menu.abstained({'rules': 12, 'unread': 5}) == (
            '12 rules for this command; none matched, and 5 of them needed'
            ' the output, which was not read')


def test_the_selector_reports_the_tally(capsys, mocker, settings):
    """`ui.select_command` says why when nothing came of the pass."""
    from thebleep import corrector, ui

    settings.no_colors = True
    mocker.patch.object(corrector, 'last_pass', {'rules': 9, 'unread': 4})
    assert ui.select_command(iter([]), Command('gti', None)) == (
        None, const.ACTION_ABORT)
    err = capsys.readouterr()[1]
    assert err.endswith('9 rules for this command; none matched, and 4 of'
                        ' them needed the output, which was not read\n')
