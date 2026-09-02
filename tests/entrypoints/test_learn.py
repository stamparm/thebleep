# -*- encoding: utf-8 -*-

from unittest.mock import Mock

import pytest

from thebleep import learning
from thebleep.entrypoints.learn import learn_from_history


@pytest.fixture(autouse=True)
def learning_home(tmpdir, settings, monkeypatch, os_environ):
    """A config directory of the test's own: the entrypoint calls
    `settings.init`, which works the directory out again from the
    environment, so setting `user_dir` alone would leave the real one in
    play."""
    os_environ['XDG_CONFIG_HOME'] = str(tmpdir)
    os_environ['HOME'] = str(tmpdir)
    monkeypatch.chdir(str(tmpdir))
    return tmpdir


@pytest.fixture(autouse=True)
def installed(mocker):
    mocker.patch('thebleep.learning._exists',
                 side_effect=lambda name: name in ('git', 'pytest'))


@pytest.fixture
def history(mocker):
    return mocker.patch('thebleep.learning.shell_history', return_value=[
        'gti status', 'git status', 'gti status', 'git status',
        'pytets -q', 'pytest -q'])


def args(mode):
    return Mock(learn_from_history=mode, debug=False, yes=False, repeat=False,
                edit=False, explain=False)


def test_list_shows_and_learns_nothing(capsys, history):
    assert learn_from_history(args('list')) == 0
    out = capsys.readouterr().out
    assert ' 1  gti -> git  (gti, seen 2)' in out
    assert ' 2  pytets -> pytest  (pytets, seen 1)' in out
    assert learning.load() == []


def test_all_learns_everything(capsys, history):
    assert learn_from_history(args('all')) == 0
    assert 'Learned 2 corrections.' in capsys.readouterr().out
    assert [entry['after'] for entry in learning.load()] == [
        'pytest -q', 'git status']


def test_ask_learns_what_was_answered_yes(capsys, history, mocker):
    mocker.patch('thebleep.ui.is_interactive', return_value=True)
    mocker.patch('thebleep.system.get_key', side_effect=['x', 'y', 'n'])
    assert learn_from_history(args('ask')) == 0
    assert [entry['before'] for entry in learning.load()] == ['gti status']
    assert 'keep it? [y/n/q]' in capsys.readouterr().err


def test_q_stops_asking(history, mocker):
    mocker.patch('thebleep.ui.is_interactive', return_value=True)
    mocker.patch('thebleep.system.get_key', side_effect=['q'])
    assert learn_from_history(args('ask')) == 0
    assert learning.load() == []


def test_ask_without_a_terminal_lists_and_says_how(capsys, history, mocker):
    mocker.patch('thebleep.ui.is_interactive', return_value=False)
    assert learn_from_history(args('ask')) == 1
    out, err = capsys.readouterr()
    assert 'gti -> git' in out
    assert '--learn-from-history all' in err
    assert learning.load() == []


def test_nothing_to_propose(capsys, mocker):
    mocker.patch('thebleep.learning.shell_history',
                 return_value=['ls', 'cd x', 'git status'])
    assert learn_from_history(args('list')) == 0
    assert 'No typo-then-fix pairs' in capsys.readouterr().out
