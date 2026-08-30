# -*- encoding: utf-8 -*-

"""A small, dependency-free MCP server for the structured Bleep API.

The stdio transport is intentionally the whole server. A client starts
``thebleep --mcp`` and sends one newline-delimited JSON-RPC message at a time.
The exposed tools only inspect command text and output supplied by the caller;
they never replay a command or inspect the host on the caller's behalf.
"""

import copy
import json
import sys

from . import api
from .utils import get_installation_version


PROTOCOL_VERSION = '2025-06-18'
MAX_MESSAGE = 16 * 1024 * 1024
_MISSING = object()


def _text_schema(description):
    return {'type': 'string', 'description': description}


def _output_schema():
    return {'anyOf': [
        {'type': 'string'},
        {'type': 'null'},
    ], 'description': 'Output already captured by the caller, if available'}


def _tool(name, title, description, properties):
    return {
        'name': name,
        'title': title,
        'description': description,
        'inputSchema': {
            'type': 'object',
            'properties': properties,
            'required': ['command'],
            'additionalProperties': False,
        },
        'outputSchema': {'type': 'object'},
        'annotations': {
            'readOnlyHint': True,
            'destructiveHint': False,
            'idempotentHint': True,
            'openWorldHint': False,
        },
    }


TOOLS = (
    _tool(
        'bleep_suggest',
        'Suggest a safer command correction',
        'Return deterministic command corrections from command text and '
        'already-captured output. This tool never runs the command.',
        {
            'command': _text_schema('The command to inspect'),
            'output': _output_schema(),
        }),
    _tool(
        'bleep_why',
        'Explain a command failure',
        'Return deterministic diagnoses and read-only next steps for a '
        'captured command failure. This tool never probes the machine.',
        {
            'command': _text_schema('The command that failed'),
            'output': _output_schema(),
            'platform': {
                'type': 'string',
                'enum': ['posix', 'nt'],
                'description': 'Target platform for follow-up commands',
            },
        }),
)

_TOOL_NAMES = frozenset(tool['name'] for tool in TOOLS)


def _response(request_id, result):
    return {'jsonrpc': '2.0', 'id': request_id, 'result': result}


def _error(request_id, code, message):
    return {'jsonrpc': '2.0', 'id': request_id,
            'error': {'code': code, 'message': message}}


def _invalid_params(request_id, message):
    return _error(request_id, -32602, message)


def _validate_initialize(params):
    if params is not None and not isinstance(params, dict):
        return 'initialize params must be an object'
    return None


def _validate_tool_arguments(name, arguments):
    if not isinstance(arguments, dict):
        return 'tool arguments must be an object'

    allowed = {'command', 'output'} | ({'platform'} if name == 'bleep_why'
                                       else set())
    unexpected = sorted(set(arguments) - allowed)
    if unexpected:
        return 'unknown argument: {}'.format(unexpected[0])
    if not isinstance(arguments.get('command'), str):
        return 'command must be a string'
    if 'output' in arguments and arguments['output'] is not None \
            and not isinstance(arguments['output'], str):
        return 'output must be a string or null'
    if name == 'bleep_why' and 'platform' in arguments \
            and arguments['platform'] not in ('posix', 'nt'):
        return "platform must be 'posix' or 'nt'"
    return None


def _call_tool(name, arguments):
    command = arguments['command']
    output = arguments.get('output')
    if name == 'bleep_why':
        return api.why(command, output, arguments.get('platform'))
    return api.suggest(command, output)


def _tool_result(value):
    return {
        'content': [{
            'type': 'text',
            'text': json.dumps(value, sort_keys=True, ensure_ascii=False),
        }],
        'structuredContent': value,
        'isError': False,
    }


def _tool_error(message):
    return {
        'content': [{'type': 'text', 'text': message}],
        'isError': True,
    }


def _handle(message, state):
    """Return ``(response, stop)`` for one decoded JSON-RPC message."""
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' \
            or not isinstance(message.get('method'), str):
        return _error(None, -32600, 'invalid request'), False

    request_id = message.get('id', _MISSING)
    is_notification = request_id is _MISSING
    method = message['method']
    params = message.get('params')

    if method == 'notifications/initialized':
        state['initialized'] = True
        return None, False
    if method == 'notifications/exit':
        return None, True
    if is_notification:
        # JSON-RPC notifications never receive a response. Unknown
        # notifications are harmless and are ignored for forward compatibility.
        return None, False

    if method == 'initialize':
        error = _validate_initialize(params)
        if error:
            return _invalid_params(request_id, error), False
        requested = params.get('protocolVersion') if params else None
        state['initialized'] = False
        return _response(request_id, {
            'protocolVersion': requested if requested == PROTOCOL_VERSION
            else PROTOCOL_VERSION,
            'capabilities': {'tools': {}},
            'serverInfo': {
                'name': 'thebleep',
                'version': get_installation_version(),
            },
            'instructions': 'Read-only deterministic command correction and '
            'failure diagnosis. Commands are never executed.',
        }), False

    if not state.get('initialized'):
        return _error(request_id, -32002, 'server is not initialized'), False

    if method == 'ping':
        return _response(request_id, {}), False
    if method == 'tools/list':
        if params is not None and not isinstance(params, dict):
            return _invalid_params(request_id,
                                   'tools/list params must be an object'), False
        if params and params.get('cursor'):
            return _invalid_params(request_id,
                                   'tool pagination is not supported'), False
        return _response(request_id, {'tools': copy.deepcopy(TOOLS)}), False
    if method == 'tools/call':
        if not isinstance(params, dict):
            return _invalid_params(request_id,
                                   'tools/call params must be an object'), False
        name = params.get('name')
        if name not in _TOOL_NAMES:
            return _invalid_params(request_id,
                                   'unknown tool: {}'.format(name)), False
        arguments = params.get('arguments', {})
        error = _validate_tool_arguments(name, arguments)
        if error:
            return _invalid_params(request_id, error), False
        try:
            value = _call_tool(name, arguments)
        except (TypeError, ValueError) as error:
            return _response(request_id, _tool_error(str(error))), False
        except Exception as error:
            # Rules are third-party extension points. Do not take down the
            # agent connection if one of them fails during a tool call.
            return _response(request_id, _tool_error(
                'The Bleep could not complete the request: {}'.format(error))), False
        return _response(request_id, _tool_result(value)), False
    if method == 'shutdown':
        return _response(request_id, None), False
    return _error(request_id, -32601, 'method not found: {}'.format(method)), False


def _write(response, stream):
    stream.write(
        json.dumps(response, separators=(',', ':'), ensure_ascii=False) + '\n')
    stream.flush()


def serve(input_stream=None, output_stream=None):
    """Serve MCP messages until EOF or ``notifications/exit``."""
    input_stream = sys.stdin if input_stream is None else input_stream
    output_stream = sys.stdout if output_stream is None else output_stream
    state = {'initialized': False}

    for line in input_stream:
        if len(line.encode('utf-8')) > MAX_MESSAGE:
            _write(_error(None, -32600, 'message exceeds the 16 MiB limit'),
                   output_stream)
            continue
        try:
            message = json.loads(line)
        except (TypeError, ValueError):
            _write(_error(None, -32700, 'parse error'), output_stream)
            continue
        response, stop = _handle(message, state)
        if response is not None:
            _write(response, output_stream)
        if stop:
            break
    return 0
