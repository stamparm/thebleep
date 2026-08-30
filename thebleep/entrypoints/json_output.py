# -*- encoding: utf-8 -*-

"""The structured command-line interface for tools calling The Bleep."""

import json
import os
import sys

from .. import api, logs
from ..conf import settings
from ..utils import format_raw_script


MAX_OUTPUT = api.MAX_OUTPUT


def _read_output(path):
    if not path:
        return None

    try:
        if path == '-':
            stream = getattr(sys.stdin, 'buffer', sys.stdin)
            output = stream.read(MAX_OUTPUT + 1)
        else:
            with open(path, 'rb') as handle:
                output = handle.read(MAX_OUTPUT + 1)
    except (OSError, UnicodeError) as error:
        logs.failed('Could not read {}: {}'.format(path, error))
        return False

    if len(output) > MAX_OUTPUT:
        logs.failed('{} is larger than the {} MiB limit'.format(
            'stdin' if path == '-' else path, MAX_OUTPUT // (1024 * 1024)))
        return False
    if isinstance(output, bytes):
        try:
            output = output.decode('utf-8')
        except UnicodeError as error:
            logs.failed('Could not read {}: {}'.format(path, error))
            return False
    return output


def json_output(args):
    """Print structured suggestions for an explicit command.

    The command is never passed through the ordinary output reader. Callers
    either provide captured output with ``--stderr`` or receive only the
    command-only rules.
    """
    settings.init(args)
    command_text = getattr(args, 'command_text', None)
    if command_text is not None and args.command:
        logs.failed('--command cannot be combined with positional command')
        return 2
    if command_text is None and not args.command:
        logs.failed('--json needs a command after the options')
        return 2
    script = (command_text if command_text is not None else
              format_raw_script(args.command))
    if not script.strip():
        logs.failed('--json needs a non-empty command')
        return 2

    output = _read_output(args.stderr)
    if output is False:
        return 2

    previous = os.getcwd()
    try:
        if args.cwd:
            os.chdir(args.cwd)
        result = api.why(
            script, output, getattr(args, 'platform_name', None)) \
            if args.why else api.suggest(script, output)
    except OSError as error:
        logs.failed('Could not use {}: {}'.format(args.cwd, error))
        return 2
    finally:
        os.chdir(previous)

    print(json.dumps(result, sort_keys=True))
    return 0
