# -*- encoding: utf-8 -*-

"""Non-executing correction of the command currently in a line editor."""

import sys

from .. import logs, types
from ..conf import settings
from ..corrector import get_corrected_commands
from ..shells import shell
from ..utils import format_raw_script


def _script(args):
    command_text = getattr(args, 'command_text', None)
    if command_text is not None and args.command:
        logs.failed('--command cannot be combined with positional command')
        return None
    value = (command_text if command_text is not None
             else format_raw_script(args.command))
    if not value.strip():
        logs.failed('--inline needs a non-empty command')
        return None
    return value


def inline_command(args):
    """Print the first command-only correction, without replaying anything."""
    settings.init(args)
    script = _script(args)
    if script is None:
        return 2

    # `None` is deliberate: Command.from_raw_script would acquire output by
    # running the command, which is exactly what an inline correction must not
    # do. Rules requiring output are consequently not candidates.
    corrected = next(iter(get_corrected_commands(types.Command(script, None))),
                     None)
    if corrected is None:
        return 1
    print(corrected.script)
    return 0


def print_binding(args):
    """Print the shell's opt-in Esc Esc line-editor binding."""
    settings.init(args)
    binding = shell.inline_binding()
    if binding is None:
        logs.failed('{} does not support inline correction bindings.'.format(
            shell.friendly_name))
        return 2
    sys.stdout.write(binding)
    return 0
