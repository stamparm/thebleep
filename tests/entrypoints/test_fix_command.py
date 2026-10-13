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
                         debug=True, why=False))
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


def test_why_with_nothing_to_explain_says_so(capsys, settings, mocker):
    """It printed nothing at all and exited 0."""
    settings.debug = False
    mocker.patch('thebleep.entrypoints.fix_command._get_raw_command',
                 return_value=[''])
    with pytest.raises(SystemExit) as raised:
        fix_command(Mock(command=[], force_command=None, repeat=False,
                         debug=False, why=True, pick=None))
    assert raised.value.code == 1
    assert 'No previous command to explain' in capsys.readouterr().err


def test_why_asks_the_explainer_only_when_nothing_was_diagnosed(
        capsys, settings, mocker):
    settings.debug = False
    mocker.patch('thebleep.entrypoints.fix_command._get_raw_command',
                 return_value=['./deploy'])
    mocker.patch('thebleep.entrypoints.fix_command.types.Command'
                 '.from_raw_script', return_value=Command(
                     './deploy', 'something nobody has a fingerprint for'))
    mocker.patch('thebleep.entrypoints.fix_command.get_corrected_commands')
    settings.why_command = 'my-explainer'
    asked = mocker.patch('thebleep.explainer.ask',
                         return_value='a plausible story')

    fix_command(Mock(command=[], force_command=None, repeat=False,
                     debug=False, why=True))

    output = capsys.readouterr().out
    assert 'No deterministic diagnosis found.' in output
    assert 'from my-explainer, which is not a deterministic source:' in output
    assert output.rstrip().endswith('a plausible story')
    asked.assert_called_once()
    assert asked.call_args[0][:2] == (
        './deploy', 'something nobody has a fingerprint for')


def test_why_does_not_ask_the_explainer_when_it_had_an_answer(
        capsys, settings, mocker):
    settings.debug = False
    mocker.patch('thebleep.entrypoints.fix_command._get_raw_command',
                 return_value=['python server.py --port 5432'])
    mocker.patch('thebleep.entrypoints.fix_command.types.Command'
                 '.from_raw_script', return_value=Command(
                     'python server.py --port 5432',
                     'OSError: [Errno 98] Address already in use'))
    mocker.patch('thebleep.entrypoints.fix_command.get_corrected_commands')
    settings.why_command = 'my-explainer'
    asked = mocker.patch('thebleep.explainer.ask')

    fix_command(Mock(command=[], force_command=None, repeat=False,
                     debug=False, why=True))

    assert 'Port 5432 is already in use.' in capsys.readouterr().out
    assert not asked.called


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


def test_a_mistyped_alias_is_not_what_gets_corrected(mocker):
    """fish hands over `$history[1]`; when that was `belep`, the alias
    mistyped, `belep` came back as `beep`. The command before it is meant."""
    mocker.patch('thebleep.entrypoints.fix_command.get_alias',
                 return_value='bleep')
    mocker.patch('thebleep.entrypoints.fix_command.get_all_executables',
                 return_value=['git', 'beep'])
    mocker.patch('thebleep.shells.shell.get_history',
                 return_value=['ls', 'git psuh', 'belep'])
    known_args = Mock(force_command=None, command=['belep'])
    assert _get_raw_command(known_args) == ['git psuh']
    # A command that is a program of its own is left alone.
    assert _get_raw_command(Mock(force_command=None, command=['beep'])) == [
        'beep']


class TestSuggestCommand(object):
    """`suggest_command`: asked only when no rule had anything, offered as one
    row that says where it came from, never run unasked."""

    @pytest.fixture
    def nothing_matched(self, mocker, settings):
        settings.debug = False
        settings.suggest_command = 'my-model'
        mocker.patch('thebleep.entrypoints.fix_command._get_raw_command',
                     return_value=['frobnicate --x'])
        mocker.patch('thebleep.entrypoints.fix_command.types.Command'
                     '.from_raw_script', return_value=Command(
                         'frobnicate --x', 'frobnicate: bad flag --x'))
        mocker.patch('thebleep.entrypoints.fix_command.get_corrected_commands',
                     return_value=iter([]))
        return mocker.patch(
            'thebleep.entrypoints.fix_command.select_command',
            return_value=(None, None))

    def test_offered_as_one_row_saying_where_from(self, nothing_matched,
                                                  mocker):
        # `fix_command` reads the settings afresh, so the setting is the
        # function that reads it.
        mocker.patch('thebleep.explainer.suggester', return_value='my-model')
        mocker.patch('thebleep.explainer._run',
                     return_value='```\n`frobnicate --y`\n```')
        with pytest.raises(SystemExit):
            fix_command(Mock(command=[], force_command=None, repeat=False,
                             debug=False, why=False, pick=None, yes=False))
        offered = list(nothing_matched.call_args[0][0])
        assert [c.script for c in offered] == ['frobnicate --y']
        assert 'my-model' in offered[0].evidence[0]
        assert offered[0].confidence is None

    def test_not_asked_when_a_rule_had_an_answer(self, mocker, settings):
        from thebleep.entrypoints import fix_command as module
        from thebleep.types import CorrectedCommand

        asked = mocker.patch('thebleep.explainer._run')
        settings.suggest_command = 'my-model'
        rows = module._or_the_suggester(
            iter([CorrectedCommand('ls', None, 1)]), Command('sl', ''))
        assert [c.script for c in rows] == ['ls']
        assert not asked.called

    def test_never_with_yes(self, mocker, settings):
        from thebleep.entrypoints import fix_command as module

        asked = mocker.patch('thebleep.explainer._run', return_value='x')
        settings.suggest_command = 'my-model'
        settings.require_confirmation = False
        assert list(module._or_the_suggester(iter([]), Command('sl', ''))) == []
        assert not asked.called
