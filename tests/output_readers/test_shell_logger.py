# -*- encoding: utf-8 -*-

import socket
import pytest

if not hasattr(socket, 'AF_UNIX'):
    pytest.skip('the shell logger is POSIX only', allow_module_level=True)

from thebleep.output_readers import shell_logger


def _client(mocker, response):
    stream = mocker.MagicMock()
    stream.readline.return_value = response
    client = mocker.MagicMock()
    client.__enter__.return_value = client
    client.makefile.return_value.__enter__.return_value = stream
    mocker.patch.object(shell_logger.socket, 'socket', return_value=client)
    return stream


def test_shell_logger_response_is_bounded(mocker, monkeypatch):
    monkeypatch.setattr(shell_logger, 'MAX_RESPONSE', 32)
    stream = _client(mocker, b'{"commands": []}\n')

    assert shell_logger._get_last_n(5) == []
    stream.readline.assert_called_once_with(33)


def test_shell_logger_rejects_an_oversized_response(mocker, monkeypatch):
    monkeypatch.setattr(shell_logger, 'MAX_RESPONSE', 8)
    _client(mocker, b'{"commands": []}' + b' ' * 20 + b'\n')

    with pytest.raises(ValueError):
        shell_logger._get_last_n(5)
