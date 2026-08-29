from tests.functional.plots import _answer


def test_answer_retries_a_key_dropped_before_raw_mode(mocker):
    timeout = object()
    process = mocker.Mock()
    process.expect.side_effect = [0, 1]

    _answer(process, timeout, '\n', 'test', attempts=2, patience=1)

    assert process.send.call_count == 2
