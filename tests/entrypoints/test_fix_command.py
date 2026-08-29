import pytest
from unittest.mock import Mock
from thebleep import const
from thebleep.types import Command
from thebleep.entrypoints.fix_command import _get_raw_command, fix_command


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


def test_debug_does_not_print_the_env_setting_values(capsys, settings, mocker):
    """`--debug` printed the whole settings object, and `env` is where people
    keep tokens.

    The previous changelog claimed debug output logged names only. That was true
    of the *replay* logger and not of this one, which runs first: `pformat` on a
    plain dict printed `{'env': {'API_TOKEN': 'super-secret-value'}}`. The
    issue template asks for debug output to be pasted into a bug report.

    """
    settings.debug = True
    settings.env = {'API_TOKEN': 'super-secret-value', 'LC_ALL': 'C'}
    mocker.patch('thebleep.entrypoints.fix_command._get_raw_command',
                 return_value=[])

    try:
        fix_command(Mock(command=[], force_command=None, repeat=False,
                         debug=True))
    except Exception:                                        # noqa: BLE001
        # What the correction does after this is somebody else's test; the
        # debug line has already been written.
        pass

    printed = capsys.readouterr()[1]
    assert 'Run with settings' in printed
    assert 'super-secret-value' not in printed
    # The name is still there, because that is the useful half.
    assert 'API_TOKEN' in printed


def test_why_prints_a_deterministic_diagnosis_without_correcting(
        capsys, settings, mocker):
    settings.debug = False
    mocker.patch('thebleep.entrypoints.fix_command._get_raw_command',
                 return_value=['python server.py --port 5432'])
    mocker.patch('thebleep.entrypoints.fix_command.types.Command'
                 '.from_raw_script', return_value=Command(
                     'python server.py --port 5432',
                     'OSError: [Errno 98] Address already in use'))
    correct = mocker.patch(
        'thebleep.entrypoints.fix_command.get_corrected_commands')

    fix_command(Mock(command=[], force_command=None, repeat=False,
                     debug=False, why=True))

    output = capsys.readouterr().out
    assert 'Port 5432 is already in use.' in output
    assert 'read-only' in output
    assert not correct.called


def test_pick_uses_stored_output_without_replaying(mocker, settings):
    stored = {'script': 'gti status', 'output': "gti: command not found",
              'cwd': '.', 'shell': 'bash', 'exit': 127, 'saved_at': 1}
    mocker.patch('thebleep.entrypoints.fix_command.failure_store.load',
                 return_value=[stored])
    mocker.patch('thebleep.entrypoints.fix_command.failure_store.record')
    correct = mocker.patch(
        'thebleep.entrypoints.fix_command.get_corrected_commands',
        return_value=[])
    select = mocker.patch(
        'thebleep.entrypoints.fix_command.select_command',
        return_value=(None, const.ACTION_ABORT))

    with pytest.raises(SystemExit):
        fix_command(Mock(command=[], force_command=None, repeat=False,
                         debug=False, why=False, pick=1))

    assert correct.call_args.args[0] == Command(
        'gti status', "gti: command not found")
    assert select.called


def test_pick_lists_without_correcting(capsys, mocker, settings):
    mocker.patch('thebleep.entrypoints.fix_command.failure_store.load',
                 return_value=[])

    fix_command(Mock(command=[], force_command=None, repeat=False,
                     debug=False, why=False, pick=0))

    assert capsys.readouterr().out == 'No recorded failures.\n'


def test_recording_survives_an_unavailable_working_directory(mocker, settings):
    mocker.patch('thebleep.entrypoints.fix_command._get_raw_command',
                 return_value=['gti'])
    mocker.patch('thebleep.entrypoints.fix_command.types.Command'
                 '.from_raw_script', return_value=Command('gti', 'not found'))
    record = mocker.patch(
        'thebleep.entrypoints.fix_command.failure_store.record')
    mocker.patch('thebleep.entrypoints.fix_command._fix_command')
    mocker.patch('thebleep.entrypoints.fix_command.os.getcwd',
                 side_effect=OSError('directory was removed'))

    fix_command(Mock(command=[], force_command=None, repeat=False,
                     debug=False, why=False, pick=None))

    assert record.call_args.args[3] == ''


def test_picked_failure_survives_an_unavailable_working_directory(mocker):
    from thebleep.entrypoints.fix_command import _picked_failure

    stored = {'script': 'gti status', 'output': 'not found', 'cwd': '.',
              'shell': 'bash', 'exit': 127, 'saved_at': 1}
    mocker.patch('thebleep.entrypoints.fix_command.failure_store.load',
                 return_value=[stored])
    mocker.patch('thebleep.entrypoints.fix_command.os.getcwd',
                 side_effect=OSError('directory was removed'))
    chdir = mocker.patch('thebleep.entrypoints.fix_command.os.chdir')

    with _picked_failure(1) as command:
        assert command == Command('gti status', 'not found')

    chdir.assert_called_once_with('.')


def test_picked_failure_ignores_a_failed_restore(mocker):
    from thebleep.entrypoints.fix_command import _picked_failure

    stored = {'script': 'gti status', 'output': 'not found', 'cwd': '.',
              'shell': 'bash', 'exit': 127, 'saved_at': 1}
    mocker.patch('thebleep.entrypoints.fix_command.failure_store.load',
                 return_value=[stored])
    mocker.patch('thebleep.entrypoints.fix_command.os.getcwd',
                 return_value='/original')
    mocker.patch('thebleep.entrypoints.fix_command.os.chdir',
                 side_effect=[None, OSError('directory was removed')])

    with _picked_failure(1) as command:
        assert command.script == 'gti status'
