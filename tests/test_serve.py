# -*- encoding: utf-8 -*-

"""The warm server: one question per connection, over a private socket."""

import os
import socket
import threading

import pytest

from thebleep import serve

pytestmark = pytest.mark.skipif(not hasattr(socket, 'AF_UNIX'),
                                reason='needs Unix sockets')


@pytest.fixture
def runtime(tmpdir, os_environ):
    """A runtime directory short enough for a socket path on every platform:
    macOS caps one at 104 bytes and its pytest temporary paths are longer."""
    import shutil
    import tempfile

    short = tempfile.mkdtemp(prefix='tb-', dir='/tmp' if os.path.isdir('/tmp')
                             else None)
    os_environ['XDG_RUNTIME_DIR'] = short
    os_environ['TB_SHELL'] = 'zsh'
    yield type(tmpdir)(short)
    shutil.rmtree(short, ignore_errors=True)


@pytest.fixture
def server(runtime, mocker):
    """A serving thread, stopped by its idle timeout after the test."""
    mocker.patch('thebleep.serve.correct',
                 side_effect=lambda script: {'gti status': 'git status',
                                             'sl': 'ls'}.get(script))
    ready = threading.Event()
    outcome = {}

    def run():
        outcome['status'] = serve.serve('zsh', idle=1.5,
                                        ready=lambda path: ready.set())

    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    assert ready.wait(10), 'the server never started listening'
    yield outcome
    thread.join(10)


class TestServing(object):
    def test_a_correction(self, server):
        assert serve.ask('zsh', 'gti status') == 'git status'

    def test_no_correction(self, server):
        assert serve.ask('zsh', 'ls -la') is None

    def test_the_aliases_travel_with_the_question(self, server, os_environ):
        serve.ask('zsh', 'gti status', aliases='g=git')
        assert os.environ.get('TB_SHELL_ALIASES') == 'g=git'
        serve.ask('zsh', 'gti status')
        assert 'TB_SHELL_ALIASES' not in os.environ

    def test_garbage_is_answered_none(self, server):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(3)
        connection.connect(serve.socket_path('zsh'))
        connection.sendall(b'not json at all\n')
        connection.shutdown(socket.SHUT_WR)
        assert connection.recv(100) == b'none\n'
        connection.close()

    def test_a_request_too_large_is_answered_none(self, server, mocker):
        mocker.patch.object(serve, 'MAX_REQUEST', 10)
        assert serve.ask('zsh', 'gti status' * 5) is None

    def test_many_questions(self, server):
        for _ in range(20):
            assert serve.ask('zsh', 'sl') == 'ls'

    def test_the_socket_is_private(self, server):
        mode = os.stat(serve.socket_path('zsh')).st_mode & 0o777
        assert mode == 0o600
        directory = os.stat(serve.socket_directory()).st_mode & 0o777
        assert directory == 0o700

    def test_it_leaves_when_idle_and_takes_the_socket_with_it(self, server):
        import time

        deadline = time.time() + 10
        while os.path.exists(serve.socket_path('zsh')) and time.time() < deadline:
            time.sleep(0.1)
        assert not os.path.exists(serve.socket_path('zsh'))
        assert server.get('status') == 0


def test_no_server_raises_for_the_client(runtime):
    with pytest.raises(OSError):
        serve.ask('zsh', 'gti status')


def test_a_shared_directory_is_refused(runtime, capsys):
    directory = serve.socket_directory()
    os.makedirs(directory)
    os.chmod(directory, 0o755)
    assert serve.serve('zsh', idle=0.1) == 2
    assert 'only you can enter' in capsys.readouterr()[1]


def test_the_socket_goes_in_the_runtime_directory(runtime):
    assert serve.socket_path('zsh') == str(
        runtime.join('thebleep', 'inline-zsh.sock'))


def test_or_in_the_cache_without_one(os_environ, tmpdir):
    os_environ.pop('XDG_RUNTIME_DIR', None)
    os_environ['XDG_CACHE_HOME'] = str(tmpdir)
    expected = str(tmpdir.join('thebleep', 'serve', 'inline-bash.sock'))
    if serve._fits(str(tmpdir.join('thebleep', 'serve'))):
        assert serve.socket_path('bash') == expected
    else:
        assert serve.socket_path('bash') != expected


def test_a_path_too_long_for_a_socket_is_not_used(os_environ, tmpdir):
    os_environ['XDG_RUNTIME_DIR'] = str(tmpdir.mkdir('x' * 120))
    path = serve.socket_path('zsh')
    assert len(path.encode('utf-8')) <= serve.MAX_SOCKET_PATH
    assert 'thebleep' in path


def test_correct_is_the_inline_correction(mocker):
    inline = mocker.patch('thebleep.entrypoints.inline.correct',
                          return_value='git status')
    assert serve.correct('gti status') == 'git status'
    inline.assert_called_once_with('gti status')
