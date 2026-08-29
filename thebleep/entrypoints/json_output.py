# -*- encoding: utf-8 -*-

"""The structured command-line interface for tools calling The Bleep."""

import json
import os

from .. import api, logs
from ..conf import settings
from ..utils import format_raw_script


def _read_output(path):
    if not path:
        return None

    try:
        with open(path, encoding='utf-8') as handle:
            return handle.read()
    except (OSError, UnicodeError) as error:
        logs.failed('Could not read {}: {}'.format(path, error))
        return False


def json_output(args):
    """Print structured suggestions for an explicit command.

    The command is never passed through the ordinary output reader. Callers
    either provide captured output with ``--stderr`` or receive only the
    command-only rules.
    """
    settings.init(args)
    if not args.command:
        logs.failed('--json needs a command after the options')
        return 2

    output = _read_output(args.stderr)
    if output is False:
        return 2

    previous = os.getcwd()
    try:
        if args.cwd:
            os.chdir(args.cwd)
        result = api.suggest(format_raw_script(args.command), output)
    except OSError as error:
        logs.failed('Could not use {}: {}'.format(args.cwd, error))
        return 2
    finally:
        os.chdir(previous)

    print(json.dumps(result, sort_keys=True))
    return 0
