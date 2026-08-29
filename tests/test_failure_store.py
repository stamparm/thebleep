from thebleep import failure_store


def test_record_keeps_recent_failures_newest_first(mocker):
    save = mocker.patch('thebleep.failure_store.cachefile.save')
    mocker.patch('thebleep.failure_store.load', return_value=[])

    failure_store.record('gti status', 'not found', '127', 'project', 'bash')

    value = save.call_args.args[2]
    assert value[0]['script'] == 'gti status'
    assert value[0]['output'] == 'not found'
    assert value[0]['exit'] == 127
    assert value[0]['cwd'] == 'project'
    assert value[0]['shell'] == 'bash'


def test_record_caps_the_ring(mocker):
    save = mocker.patch('thebleep.failure_store.cachefile.save')
    old = [{'script': str(index), 'output': '', 'cwd': '.', 'shell': 'bash',
            'exit': 1, 'saved_at': index} for index in range(5)]
    mocker.patch('thebleep.failure_store.load', return_value=old)

    failure_store.record('new', '', 1, '.', 'bash')

    value = save.call_args.args[2]
    assert [entry['script'] for entry in value] == [
        'new', '0', '1', '2', '3']


def test_record_does_not_store_success_or_invalid_status(mocker):
    save = mocker.patch('thebleep.failure_store.cachefile.save')

    failure_store.record('true', '', 0)
    failure_store.record('false', '', 'unknown')

    assert not save.called


def test_forget_removes_one_failure(mocker):
    save = mocker.patch('thebleep.failure_store.cachefile.save')
    entries = [
        {'script': 'first', 'output': '', 'cwd': 'project', 'shell': 'bash',
         'exit': 1, 'saved_at': 1},
        {'script': 'second', 'output': '', 'cwd': 'project', 'shell': 'bash',
         'exit': 1, 'saved_at': 2}]
    mocker.patch('thebleep.failure_store.load', return_value=entries)

    assert failure_store.forget(1)
    assert [entry['script'] for entry in save.call_args.args[2]] == ['second']


def test_forget_rejects_missing_failure(mocker):
    save = mocker.patch('thebleep.failure_store.cachefile.save')
    mocker.patch('thebleep.failure_store.load', return_value=[])

    assert not failure_store.forget(1)
    assert not save.called


def test_output_is_bounded_at_both_ends():
    output = 'a' * failure_store.MAX_OUTPUT + 'tail'

    result = failure_store._clip_output(output)

    assert len(result) == failure_store.MAX_OUTPUT
    assert result.startswith('a')
    assert result.endswith('tail')
    assert '[output clipped]' in result


def test_load_discards_malformed_entries(mocker):
    valid = {'script': 'gti', 'output': '', 'cwd': 'project', 'shell': 'bash',
             'exit': 127, 'saved_at': 1}
    mocker.patch('thebleep.failure_store.cachefile.load',
                 return_value=[valid, {'script': 'not enough'}])

    assert failure_store.load() == [valid]


def test_print_recent(capsys):
    failure_store.print_recent([{
        'script': 'gti status', 'output': '', 'cwd': 'project', 'shell': 'bash',
        'exit': 127, 'saved_at': 1}])

    output = capsys.readouterr().out
    assert 'Recent failures:' in output
    assert '1  gti status  (exit 127, project)' in output
