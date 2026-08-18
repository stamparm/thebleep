import pytest
from unittest.mock import Mock
from thebleep import const
from thebleep.entrypoints.fix_command import _get_raw_command


class TestGetRawCommand(object):
    def test_from_force_command_argument(self):
        known_args = Mock(force_command='git brunch')
        assert _get_raw_command(known_args) == ['git brunch']

    def test_from_command_argument(self, os_environ):
        os_environ['TB_HISTORY'] = None
        known_args = Mock(force_command=None,
                          command=['sl'])
        assert _get_raw_command(known_args) == ['sl']

    @pytest.mark.parametrize('history, result', [
        ('git br', 'git br'),
        ('git br\nbelep', 'git br'),
        ('git br\nbelep\nls', 'ls'),
        ('git br\nbelep\nls\nblep', 'ls')])
    def test_from_history(self, os_environ, history, result):
        os_environ['TB_HISTORY'] = history
        known_args = Mock(force_command=None,
                          command=None)
        assert _get_raw_command(known_args) == [result]

    def test_a_cut_history_line_is_not_a_command(self, os_environ):
        """What is left of a line longer than the whole window is a fragment.

        Correcting half of a command and running the result is worse than not
        correcting it, so it is passed over for the newest whole line.

        """
        fragment = 'x' * const.TRANSPORT_LIMIT
        os_environ['TB_HISTORY'] = '{}\ngit br\nbleep'.format(fragment)
        known_args = Mock(force_command=None, command=None)
        assert _get_raw_command(known_args) == ['git br']

    def test_nothing_is_offered_when_only_a_fragment_is_left(self, os_environ):
        os_environ['TB_HISTORY'] = 'x' * const.TRANSPORT_LIMIT
        known_args = Mock(force_command=None, command=None)
        assert _get_raw_command(known_args) == []
