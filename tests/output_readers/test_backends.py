# -*- encoding: utf-8 -*-

import pytest

from thebleep.output_readers import backends


@pytest.fixture(autouse=True)
def no_registered_backends():
    backends.clear_registered()
    yield
    backends.clear_registered()


def test_builtins_keep_replay_as_the_last_fallback(settings):
    settings.instant_mode = True

    assert [(item.name, item.replayless)
            for item in backends.builtins('gti status', 'error')] == [
                ('shell-logger', True), ('instant-log', True),
                ('tmux', True), ('replay', False)]


def test_a_registered_backend_runs_before_builtins(mocker):
    read = mocker.Mock(return_value='captured')
    backend = backends.CaptureBackend('tmux', True, lambda: True, read)
    backends.register(backend)

    assert backends.read('gti status', 'error') == 'captured'
    read.assert_called_once_with('gti status', 'error')


def test_a_backend_that_cannot_answer_falls_through(mocker):
    read = mocker.Mock(return_value=None)
    backend = backends.CaptureBackend('empty', True, lambda: True, read)
    backends.register(backend)
    mocker.patch.object(backends, '_shell_logger_available', return_value=False)
    mocker.patch.object(backends, '_instant_available', return_value=False)
    mocker.patch.object(backends, '_replay_available', return_value=False)

    assert backends.read('gti status', 'error') is None
    read.assert_called_once_with('gti status', 'error')


def test_duplicate_backend_names_are_rejected():
    backend = backends.CaptureBackend('tmux', True, lambda: True, lambda *_: '')
    backends.register(backend)

    with pytest.raises(ValueError):
        backends.register(backend)


def test_status_does_not_execute_a_command(settings, mocker):
    mocker.patch('thebleep.shells.shell.supports_instant_mode',
                 return_value=True)
    settings.instant_mode = False

    assert [item['name'] for item in backends.status()] == [
        'shell-logger', 'instant-log', 'tmux', 'replay']
    assert backends.status()[2]['configured'] is False
    assert not any(item['available'] for item in backends.status()
                   if item['name'] not in ('replay',))


def test_status_includes_registered_backend_health():
    backends.register(backends.CaptureBackend(
        'custom', True, lambda: False, lambda *_: None))

    assert backends.status()[0] == {
        'name': 'custom', 'replayless': True,
        'configured': True, 'available': False}
