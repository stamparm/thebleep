# -*- encoding: utf-8 -*-

"""`--stats`: a local, bounded record of what the tool has been doing."""

import json
import time

import pytest

from thebleep import stats


@pytest.fixture(autouse=True)
def stats_home(tmpdir, settings):
    from thebleep.system import Path

    settings.user_dir = Path(str(tmpdir))
    return tmpdir


class TestCounting(object):
    def test_starts_empty(self):
        record = stats.load()
        assert record['accepted'] == 0
        assert record['slips'] == {} and record['rules'] == {}
        assert abs(record['since'] - time.time()) < 5

    def test_an_accepted_correction_counts_its_rule_and_slip(self, stats_home):
        stats.bump('accepted', rule='no_command', before='gti status',
                   after='git status')
        stats.bump('accepted', rule='no_command', before='gti push',
                   after='git push')
        stats.bump('edited', rule='git_not_command', before='git satus',
                   after='git status')
        record = stats.load()
        assert record['accepted'] == 2 and record['edited'] == 1
        assert record['rules'] == {'no_command': 2, 'git_not_command': 1}
        assert record['slips'] == {u'gti → git': 2, u'satus → status': 1}
        stored = json.loads(stats_home.join('stats.json').read_text('utf-8'))
        assert stored['format'] == 1

    def test_a_correction_that_changes_more_than_a_word_keeps_no_text(self):
        stats.bump('accepted', rule='wrong_directory', before='npm run build',
                   after='cd app && npm run build')
        record = stats.load()
        assert record['accepted'] == 1
        assert record['slips'] == {}
        assert record['rules'] == {'wrong_directory': 1}

    def test_trusted_and_abstained(self):
        stats.bump('trusted')
        stats.bump('abstained')
        stats.bump('abstained')
        record = stats.load()
        assert record['trusted'] == 1 and record['abstained'] == 2

    def test_an_unknown_counter_counts_nothing(self):
        stats.bump('exploded')
        assert stats.load() == dict(stats.load(), accepted=0)

    def test_the_tables_are_bounded(self, mocker):
        mocker.patch.object(stats, 'TOP', 3)
        # Most frequent first, so what is trimmed is what was seen least.
        for name in ('e', 'd', 'c', 'b', 'a'):
            for _ in range(ord(name) - ord('a') + 1):
                stats.bump('accepted', rule=name)
        assert stats.load()['rules'] == {'e': 5, 'd': 4, 'c': 3}

    def test_reset(self):
        stats.bump('accepted', rule='x')
        assert stats.reset()
        assert stats.load()['accepted'] == 0


class TestBadFiles(object):
    def test_garbage_is_a_fresh_record(self, stats_home):
        stats_home.join('stats.json').write('not json')
        assert stats.load()['accepted'] == 0

    def test_a_wrong_format_is_a_fresh_record(self, stats_home):
        stats_home.join('stats.json').write(json.dumps({'format': 9,
                                                        'accepted': 5}))
        assert stats.load()['accepted'] == 0

    def test_bad_values_are_dropped_and_good_ones_kept(self, stats_home):
        stats_home.join('stats.json').write(json.dumps({
            'format': 1, 'accepted': 'many', 'edited': 3, 'since': 0,
            'slips': {'a → b': 'x', 'c → d': 2}, 'rules': 'nope'}))
        record = stats.load()
        assert record['accepted'] == 0 and record['edited'] == 3
        assert record['slips'] == {'c → d': 2} and record['rules'] == {}

    def test_an_oversized_file_is_a_fresh_record(self, stats_home, mocker):
        mocker.patch.object(stats, 'MAX_FILE', 10)
        stats_home.join('stats.json').write(json.dumps({'format': 1,
                                                        'accepted': 5}))
        assert stats.load()['accepted'] == 0

    def test_nowhere_to_write_never_raises(self, settings, mocker):
        from thebleep.system import Path

        settings.user_dir = Path('~')
        stats.bump('accepted', rule='x')
        assert stats.load()['accepted'] == 0


class TestReport(object):
    def test_nothing_yet(self):
        lines = stats.report()
        assert lines[0].endswith('0 corrections')
        assert 'nothing yet' in lines[-1]

    def test_the_numbers_and_the_tables(self):
        for _ in range(3):
            stats.bump('accepted', rule='no_command', before='gti s',
                       after='git s')
        stats.bump('edited', rule='option_typo', before='ls --colour',
                   after='ls --color')
        stats.bump('trusted')
        stats.bump('abstained')
        lines = stats.report()
        assert lines[0].endswith('4 corrections')
        assert lines[1] == '  accepted 3, edited 1, ran without asking 1'
        assert lines[2] == '  nothing to offer 1 time'
        assert 'Most fixed:' in lines
        assert lines[lines.index('Most fixed:') + 1] == u'      3  gti → git'
        assert lines[lines.index('Rules that fixed most:') + 1] == \
            '      3  no_command'

    def test_print_report_and_reset(self, capsys):
        stats.bump('accepted', rule='x')
        assert stats.print_report('show') == 0
        assert '1 correction' in capsys.readouterr().out
        assert stats.print_report('reset') == 0
        assert 'Stats reset.' in capsys.readouterr().out
        assert stats.load()['accepted'] == 0


def test_the_correction_path_counts(mocker, settings, stats_home):
    """`fix_command` counts what the user did with the suggestion."""
    from unittest.mock import Mock

    from thebleep import const
    from thebleep.entrypoints.fix_command import _fix_command
    from thebleep.types import Command, CorrectedCommand, Rule

    rule = Rule('some_rule', lambda _: True, lambda _: 'x', True, None, 1000,
                False)
    chosen = CorrectedCommand('git status', None, 1000, rule=rule)
    mocker.patch('thebleep.entrypoints.fix_command.get_corrected_commands',
                 return_value=iter([chosen]))
    mocker.patch('thebleep.entrypoints.fix_command.select_command',
                 return_value=(chosen, const.ACTION_SELECT))
    ran = mocker.patch.object(CorrectedCommand, 'run')
    _fix_command(Mock(why=False), Command('gti status', None))
    assert ran.called
    record = stats.load()
    assert record['accepted'] == 1
    assert record['rules'] == {'some_rule': 1}
    assert record['slips'] == {u'gti → git': 1}
