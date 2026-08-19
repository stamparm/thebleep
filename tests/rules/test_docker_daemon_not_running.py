# -*- coding: utf-8 -*-

"""Docker installed, nothing listening on its socket.

Both spellings are real: the first is what Docker said up to 24, the second is
what Docker 25 and later say.

"""

import pytest
from thebleep.rules.docker_daemon_not_running import match, get_new_command
from thebleep.types import Command

OLD = (u'Cannot connect to the Docker daemon at unix:///var/run/docker.sock.'
       u' Is the docker daemon running?\n'
       u"See 'docker run --help'.\n")
NEW = (u'failed to connect to the docker API at unix:///var/run/docker.sock;'
       u' check if the path is correct and if the daemon is running:'
       u' dial unix /var/run/docker.sock: connect: no such file or directory\n')


@pytest.fixture(autouse=True)
def systemctl(mocker):
    return mocker.patch(
        'thebleep.rules.docker_daemon_not_running.which',
        return_value='/usr/bin/systemctl')


@pytest.mark.parametrize('script, output', [
    ('docker ps', OLD),
    ('docker ps', NEW),
    ('docker run bash sleep 100', OLD),
    ('docker-compose up', NEW),
])
def test_match(script, output):
    assert match(Command(script, output))


@pytest.mark.parametrize('script, output', [
    ('docker ps', 'CONTAINER ID   IMAGE'),
    ('docker run nosuchimage', 'Unable to find image'),
    ('kubectl get pods', OLD),
])
def test_not_match(script, output):
    assert not match(Command(script, output))


def test_not_match_without_systemctl(systemctl):
    """`service`, `open -a Docker` and the rest are each right somewhere else,
    and a suggestion that starts nothing is worse than none."""
    systemctl.return_value = None
    assert not match(Command('docker ps', OLD))


@pytest.mark.parametrize('script, fixed', [
    ('docker ps', 'sudo systemctl start docker && docker ps'),
    ('docker run bash sleep 100',
     'sudo systemctl start docker && docker run bash sleep 100'),
])
def test_get_new_command(script, fixed):
    assert get_new_command(Command(script, OLD)) == fixed
