# -*- coding: utf-8 -*-

"""Working out which shell we are under by walking up the process tree.

Only reached when the alias did not say, which is also when the tree is least
likely to cooperate: the parent may exit while we are reading it, and after a
`sudo su` session the processes above us belong to root.

"""

import psutil
import pytest
from thebleep import shells
from thebleep.shells.generic import Generic

UNREADABLE = [
    psutil.AccessDenied,
    psutil.NoSuchProcess,
    psutil.ZombieProcess,
    psutil.TimeoutExpired,
    PermissionError,
]


def _process(name, parent=None):
    process = type('P', (), {})()
    process.pid = 42
    process.name = lambda: name
    process.parent = lambda: parent
    return process


def test_the_shell_in_the_tree_is_found(mocker):
    shell = _process('bash', parent=None)
    mocker.patch('psutil.Process', return_value=_process('python', shell))
    assert isinstance(shells._get_shell_from_proc(), shells.Bash)


@pytest.mark.parametrize('error', UNREADABLE)
def test_an_unreadable_first_process(mocker, error):
    mocker.patch('psutil.Process', side_effect=_raise(error))
    assert isinstance(shells._get_shell_from_proc(), Generic)


@pytest.mark.parametrize('error', UNREADABLE)
def test_an_unreadable_name(mocker, error):
    process = _process('python')
    process.name = _raise(error)
    mocker.patch('psutil.Process', return_value=process)
    assert isinstance(shells._get_shell_from_proc(), Generic)


@pytest.mark.parametrize('error', UNREADABLE)
def test_an_unreadable_parent(mocker, error):
    """What happens on the way back out of `sudo su`."""
    process = _process('python')
    process.parent = _raise(error)
    mocker.patch('psutil.Process', return_value=process)
    assert isinstance(shells._get_shell_from_proc(), Generic)


def _raise(error):
    def raiser(*args, **kwargs):
        if error is psutil.NoSuchProcess:
            raise error(42)
        if error is psutil.ZombieProcess:
            raise error(42)
        if error is psutil.TimeoutExpired:
            raise error(1)
        raise error()

    return raiser


def test_nushell_in_the_tree_is_found(mocker):
    """Nushell calls itself `nu`, which is what the process is named."""
    shell = _process('nu', parent=None)
    mocker.patch('psutil.Process', return_value=_process('python', shell))
    assert isinstance(shells._get_shell_from_proc(), shells.Nushell)
