import pytest
import json
import os
import stat
import time
from pathlib import Path
from unittest.mock import MagicMock
from thebleep.shells.generic import ShellConfiguration
from thebleep.entrypoints.not_configured import main


@pytest.fixture(autouse=True)
def tracker(mocker, tmpdir):
    """A real file in a real directory, not a mocked `open`.

    The tracker used to be a predictable name in a shared `/tmp` written with
    `path.open('w')`, and these fixtures mocked that `open` -- so nothing here
    ever touched a filesystem, and the secure-creation flags that replaced it
    (`O_NOFOLLOW`, 0600) would have gone untested. A `tmpdir` costs nothing and
    holds the code to what it actually does.

    """
    path = Path(str(tmpdir)).joinpath('tracker')
    mocker.patch(
        'thebleep.entrypoints.not_configured'
        '._get_not_configured_usage_tracker_path',
        return_value=path)
    return path


def _assert_tracker_updated(tracker, pid):
    with tracker.open() as handle:
        assert json.load(handle)['pid'] == pid


def _change_tracker(tracker, pid, when=None):
    """A tracker from an earlier run -- an hour ago unless told otherwise."""
    with tracker.open('w') as handle:
        json.dump({'pid': pid,
                   'time': time.time() - 3600 if when is None else when},
                  handle)


@pytest.fixture(autouse=True)
def shell_pid(mocker):
    return mocker.patch('thebleep.entrypoints.not_configured._get_shell_pid',
                        new_callable=MagicMock)


@pytest.fixture(autouse=True)
def shell(mocker):
    shell = mocker.patch('thebleep.entrypoints.not_configured.shell',
                         new_callable=MagicMock)
    shell.get_history.return_value = []
    shell.how_to_configure.return_value = ShellConfiguration(
        content='eval $(thebleep --alias)',
        path='/tmp/.bashrc',
        reload='bash',
        can_configure_automatically=True)
    return shell


@pytest.fixture(autouse=True)
def shell_config(mocker):
    path_mock = mocker.patch('thebleep.entrypoints.not_configured.expanduser',
                             new_callable=MagicMock)
    return path_mock.return_value \
        .open.return_value \
        .__enter__.return_value


@pytest.fixture(autouse=True)
def logs(mocker):
    return mocker.patch('thebleep.entrypoints.not_configured.logs',
                        new_callable=MagicMock)


def test_for_generic_shell(shell, logs):
    shell.how_to_configure.return_value = None
    main()
    logs.how_to_configure_alias.assert_called_once()


def test_on_first_run(tracker, shell_pid, logs):
    shell_pid.return_value = 12
    main()
    _assert_tracker_updated(tracker, 12)
    logs.how_to_configure_alias.assert_called_once()


def test_on_run_after_other_commands(tracker, shell_pid, shell, logs):
    shell_pid.return_value = 12
    shell.get_history.return_value = ['bleep', 'ls']
    _change_tracker(tracker, 12)
    main()
    logs.how_to_configure_alias.assert_called_once()


def test_on_first_run_from_current_shell(tracker, shell_pid,
                                         shell, logs):
    shell.get_history.return_value = ['bleep']
    shell_pid.return_value = 12
    main()
    _assert_tracker_updated(tracker, 12)
    logs.how_to_configure_alias.assert_called_once()


def test_when_cant_configure_automatically(shell_pid, shell, logs):
    shell_pid.return_value = 12
    shell.how_to_configure.return_value = ShellConfiguration(
        content='eval $(thebleep --alias)',
        path='/tmp/.bashrc',
        reload='bash',
        can_configure_automatically=False)
    main()
    logs.how_to_configure_alias.assert_called_once()


def test_when_already_configured(tracker, shell_pid,
                                 shell, shell_config, logs):
    shell.get_history.return_value = ['bleep']
    shell_pid.return_value = 12
    _change_tracker(tracker, 12)
    shell_config.read.return_value = 'eval $(thebleep --alias)'
    main()
    logs.already_configured.assert_called_once()


def test_when_successfully_configured(tracker, shell_pid,
                                      shell, shell_config, logs):
    shell.get_history.return_value = ['bleep']
    shell_pid.return_value = 12
    _change_tracker(tracker, 12)
    shell_config.read.return_value = ''
    main()
    shell_config.write.assert_any_call('eval $(thebleep --alias)')
    logs.configured_successfully.assert_called_once()


class TestTheTracker(object):
    """A file this program writes into a directory shared with everybody.

    Or rather one it used to. `/tmp/thebleep.last_not_configured_run_<me>` is a
    name anybody can work out, and it was opened `'w'` -- so a symlink planted
    there beforehand was followed, and whatever it pointed at was truncated.
    Its own sibling, `entrypoints.shell_logger._open_log`, had always got this
    right; this had not.

    """

    def test_it_lives_under_the_users_own_cache(self, mocker, tmpdir):
        from thebleep.entrypoints import not_configured

        mocker.patch('thebleep.cachefile.directory',
                     return_value=Path(str(tmpdir)))
        path = not_configured._get_not_configured_usage_tracker_path()
        assert str(path).startswith(str(tmpdir))

    def test_a_symlink_in_its_place_is_refused(self, tracker, shell_pid, logs,
                                               tmpdir):
        from thebleep.entrypoints import not_configured

        victim = Path(str(tmpdir)).joinpath('important')
        victim.write_text(u'do not lose this')
        os.symlink(str(victim), str(tracker))

        shell_pid.return_value = 12
        not_configured._record_first_run()

        assert victim.read_text() == 'do not lose this'

    def test_it_is_not_readable_by_anybody_else(self, tracker, shell_pid):
        from thebleep.entrypoints import not_configured

        shell_pid.return_value = 12
        not_configured._record_first_run()
        assert stat.S_IMODE(tracker.stat().st_mode) == 0o600

    def test_a_cache_it_cannot_write_to_is_not_fatal(self, mocker, shell_pid,
                                                     logs):
        """Showing the instructions twice beats failing."""
        from thebleep.entrypoints import not_configured

        mocker.patch.object(not_configured, '_mkdir',
                            side_effect=OSError('read-only'))
        shell_pid.return_value = 12
        not_configured._record_first_run()

    def test_a_tracker_with_no_time_is_not_recent(
            self, tracker, shell_pid, shell):
        """`info.get('time', 0)` read a missing time as 1970, which after the
        subtraction is a run that happened moments ago -- so any file at all
        with the right pid in it authorised editing the shell's startup file."""
        from thebleep.entrypoints import not_configured

        shell_pid.return_value = 12
        shell.get_history.return_value = ['ls']
        with tracker.open('w') as handle:
            json.dump({'pid': 12}, handle)
        assert not not_configured._is_second_run()

    def test_a_shell_with_no_parent_is_not_a_second_run(self, tracker,
                                                        shell_pid):
        from thebleep.entrypoints import not_configured

        shell_pid.return_value = None
        _change_tracker(tracker, None)
        assert not not_configured._is_second_run()
