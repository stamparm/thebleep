import json

from thebleep import mcp


def _message(method, request_id=1, params=None):
    value = {'jsonrpc': '2.0', 'id': request_id, 'method': method}
    if params is not None:
        value['params'] = params
    return value


def _serve(messages):
    from io import StringIO

    incoming = StringIO('\n'.join(json.dumps(item) for item in messages) + '\n')
    outgoing = StringIO()
    assert mcp.serve(incoming, outgoing) == 0
    return [json.loads(line) for line in outgoing.getvalue().splitlines()]


def test_initialize_and_list_tools():
    responses = _serve([
        _message('initialize', params={'protocolVersion': mcp.PROTOCOL_VERSION}),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/list'),
    ])

    assert responses[0]['result']['protocolVersion'] == mcp.PROTOCOL_VERSION
    assert responses[0]['result']['capabilities'] == {'tools': {}}
    assert [tool['name'] for tool in responses[1]['result']['tools']] == [
        'bleep_suggest', 'bleep_why', 'bleep_history']
    assert all(tool['annotations']['readOnlyHint']
               for tool in responses[1]['result']['tools'])


def test_notifications_do_not_pollute_stdout():
    responses = _serve([
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'method': 'notifications/exit'},
    ])

    assert responses == []


def test_suggest_returns_structured_api_result(mocker):
    result = {'schema': 2, 'decision': 'abstain', 'suggestions': []}
    suggest = mocker.patch.object(mcp.api, 'suggest', return_value=result)
    responses = _serve([
        _message('initialize'),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/call', params={
            'name': 'bleep_suggest',
            'arguments': {'command': 'gti status', 'output': 'not found'},
        }),
    ])

    suggest.assert_called_once_with('gti status', 'not found')
    assert responses[1]['result']['structuredContent'] == result
    assert json.loads(responses[1]['result']['content'][0]['text']) == result
    assert responses[1]['result']['isError'] is False


def test_why_passes_platform_to_diagnostics(mocker):
    result = {'schema': 2, 'decision': 'abstain', 'diagnoses': []}
    why = mocker.patch.object(mcp.api, 'why', return_value=result)
    responses = _serve([
        _message('initialize'),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/call', params={
            'name': 'bleep_why',
            'arguments': {'command': 'curl example.invalid',
                          'output': 'Could not resolve host',
                          'platform': 'nt'},
        }),
    ])

    why.assert_called_once_with('curl example.invalid',
                                'Could not resolve host', 'nt')
    assert responses[1]['result']['structuredContent'] == result


def test_history_returns_local_records_without_command_arguments(mocker):
    result = {'schema': 2, 'limit': 5, 'failures': []}
    history = mocker.patch.object(mcp.api, 'history', return_value=result)
    responses = _serve([
        _message('initialize'),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/call', params={
            'name': 'bleep_history', 'arguments': {},
        }),
    ])

    history.assert_called_once_with()
    assert responses[1]['result']['structuredContent'] == result


def test_history_rejects_unexpected_arguments():
    responses = _serve([
        _message('initialize'),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/call', params={
            'name': 'bleep_history', 'arguments': {'command': 'gti'},
        }),
    ])

    assert responses[1]['error']['code'] == -32602


def test_tool_input_errors_are_visible_to_the_agent():
    responses = _serve([
        _message('initialize'),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/call', params={
            'name': 'bleep_suggest', 'arguments': {'command': ''}}),
    ])

    assert responses[1]['result']['isError'] is True
    assert 'non-empty' in responses[1]['result']['content'][0]['text']


def test_malformed_tool_arguments_are_protocol_errors():
    responses = _serve([
        _message('initialize'),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/call', params={
            'name': 'bleep_suggest', 'arguments': {'command': 17}}),
    ])

    assert responses[1]['error']['code'] == -32602


def test_protocol_errors_and_lifecycle():
    responses = _serve([
        _message('tools/list'),
        {'jsonrpc': '2.0', 'id': 2, 'method': 'unknown'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'initialize', 'params': []},
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {
            'name': 'missing', 'arguments': {}}},
    ])

    assert responses[0]['error']['code'] == -32002
    assert responses[1]['error']['code'] == -32002
    assert responses[2]['error']['code'] == -32602
    assert responses[3]['error']['code'] == -32002


def test_parse_error_is_a_json_rpc_error():
    from io import StringIO

    outgoing = StringIO()
    mcp.serve(StringIO('{bad\n'), outgoing)

    assert json.loads(outgoing.getvalue())['error']['code'] == -32700


def test_api_failure_is_a_tool_error_not_a_server_crash(mocker):
    mocker.patch.object(mcp.api, 'suggest', side_effect=RuntimeError('rule broke'))
    responses = _serve([
        _message('initialize'),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        _message('tools/call', params={
            'name': 'bleep_suggest', 'arguments': {'command': 'gti'}}),
    ])

    assert responses[1]['result']['isError'] is True
    assert 'rule broke' in responses[1]['result']['content'][0]['text']
