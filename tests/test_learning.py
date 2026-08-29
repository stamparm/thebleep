# -*- coding: utf-8 -*-

import json
import os
import stat

import pytest

from thebleep import learning
from thebleep.system import Path
from thebleep.types import Command


@pytest.fixture
def learning_home(tmpdir, settings, monkeypatch):
    directory = Path(str(tmpdir))
    settings.user_dir = directory
    monkeypatch.chdir(str(tmpdir))
    return tmpdir


def _pending(learning_home, before='corpctl deply payments',
             after='corpctl deploy payments', shell_name='generic'):
    assert learning.remember_pending(
        before, after, cwd=str(learning_home), shell_name=shell_name)


def test_pending_correction_is_promoted_to_bounded_json(learning_home):
    _pending(learning_home)

    learned = learning.learn_last('executable')

    assert learned['before'] == 'corpctl deply payments'
    assert learned['after'] == 'corpctl deploy payments'
    assert learned['scope'] == 'executable'
    assert learning.load() == [learned]
    assert json.loads(learning_home.join('learned.json').read())['format'] == 1
    assert learning._read('learning-pending.json')['entry'] is None


def test_learned_correction_matches_its_exact_command_shape(learning_home):
    _pending(learning_home)
    learning.learn_last()

    corrections = list(learning.corrections(
        Command('corpctl deply payments', '')))

    assert [correction.script for correction in corrections] == [
        'corpctl deploy payments']
    assert corrections[0].rule.name.startswith('learned_')
    assert corrections[0].rule.requires_output is False


def test_learned_correction_explains_its_scope(learning_home):
    from thebleep.explain import describe

    learning_home.mkdir('.git')
    _pending(learning_home)
    learning.learn_last('repository')
    correction = list(learning.corrections(
        Command('corpctl deply payments', '')))[0]

    assert ('matched', 'your repository learned correction for corpctl') \
        in describe(correction, Command('corpctl deply payments', ''))


def test_learned_correction_does_not_match_another_command(learning_home):
    _pending(learning_home)
    learning.learn_last()

    assert list(learning.corrections(Command('other deply payments', ''))) == []


def test_learned_words_are_quoted_when_rendered(learning_home):
    _pending(learning_home, before='corpctl deply',
             after="corpctl 'deploy;touch SHOULD_NOT_RUN'")
    learning.learn_last()

    correction = list(learning.corrections(
        Command('corpctl deply', '')))[0]

    assert correction.script == "corpctl 'deploy;touch SHOULD_NOT_RUN'"


def test_global_learning_survives_a_change_of_directory(learning_home, tmpdir,
                                                        monkeypatch):
    _pending(learning_home)
    learning.learn_last('global')
    monkeypatch.chdir(str(tmpdir.mkdir('elsewhere')))

    assert [item.script for item in learning.corrections(
        Command('corpctl deply payments', ''))] == [
            'corpctl deploy payments']


def test_repository_learning_is_limited_to_the_repository(learning_home,
                                                          tmpdir, monkeypatch):
    root = tmpdir.mkdir('repo')
    root.mkdir('.git')
    worktree = root.mkdir('work')
    monkeypatch.chdir(str(worktree))
    _pending(root)
    assert learning.learn_last('repository')['root'] == str(root)

    assert list(learning.corrections(
        Command('corpctl deply payments', '')))
    monkeypatch.chdir(str(tmpdir.mkdir('outside')))
    assert list(learning.corrections(
        Command('corpctl deply payments', ''))) == []


def test_repository_learning_requires_a_repository(learning_home):
    _pending(learning_home)

    assert learning.learn_last('repository') is None
    assert learning.load() == []


@pytest.mark.parametrize('before, after', [
    ('corpctl deply payments', 'corpctl deploy payments extra'),
    ('corpctl deply payments', 'corpctl deploy payments && notify'),
    ('corpctl deply payments', 'corpctl deploy all'),
])
def test_only_one_word_simple_corrections_can_be_learned(
        learning_home, before, after):
    assert not learning.remember_pending(
        before, after, cwd=str(learning_home), shell_name='generic')
    assert learning._read('learning-pending.json') is None


def test_side_effects_are_not_recorded_by_the_caller(mocker, learning_home):
    pending = mocker.patch.object(learning, 'remember_pending')
    from thebleep.types import CorrectedCommand

    CorrectedCommand('corpctl deploy payments', lambda *_: None, 50).run(
        Command('corpctl deply payments', ''))

    assert not pending.called


def test_forget_removes_a_learned_entry(learning_home):
    _pending(learning_home)
    learning.learn_last()

    assert learning.forget(1)
    assert learning.load() == []
    assert not learning.forget(1)


def test_malformed_or_oversized_files_are_ignored(learning_home):
    learning_home.join('learned.json').write('{not json')
    assert learning.load() == []
    learning_home.join('learned.json').write('x' * (learning.MAX_FILE + 1))
    assert learning.load() == []


def test_a_corrupt_entry_with_multiple_changes_is_ignored(learning_home):
    _pending(learning_home)
    entry = learning.learn_last()
    entry['after_parts'][2] = 'all'
    learning_home.join('learned.json').write(json.dumps({
        'format': learning.FORMAT, 'entries': [entry]}))

    assert learning.load() == []


def test_an_unexpanded_config_path_is_never_created(settings, tmpdir,
                                                    monkeypatch):
    settings.user_dir = Path('~/.thebleep')
    monkeypatch.chdir(str(tmpdir))

    assert not learning.remember_pending(
        'corpctl deply', 'corpctl deploy', cwd=str(tmpdir))
    assert not tmpdir.join('~').check()


def test_print_entries_has_a_stable_empty_result(capsys, learning_home):
    learning.print_entries()

    assert capsys.readouterr().out == 'No learned corrections.\n'


@pytest.mark.skipif(not hasattr(os, 'geteuid'),
                    reason='Windows has no POSIX mode to check')
def test_learning_store_is_private(learning_home):
    _pending(learning_home)

    assert stat.S_IMODE(os.stat(str(learning_home.join(
        'learning-pending.json'))).st_mode) == 0o600


def test_failed_exclusive_create_does_not_remove_an_existing_temp(
        learning_home, mocker):
    open_file = mocker.patch.object(
        learning.os, 'open', side_effect=FileExistsError())
    unlink = mocker.patch.object(learning.os, 'unlink')

    assert not learning._write('probe.json', {'value': 1})
    open_file.assert_called_once()
    assert not unlink.called


@pytest.mark.skipif(not hasattr(os, 'O_NOFOLLOW'),
                    reason='platform has no no-follow open flag')
def test_learning_state_does_not_follow_a_symlink(learning_home):
    target = learning_home.join('target.json')
    target.write(json.dumps({'format': learning.FORMAT, 'entries': []}))
    os.symlink(str(target), str(learning_home.join('learned.json')))

    assert learning.load() == []
