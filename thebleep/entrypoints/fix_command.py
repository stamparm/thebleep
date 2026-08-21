import os
import sys
from .. import logs, types, const
from ..conf import settings
from ..corrector import get_corrected_commands
from ..exceptions import EmptyCommand
from ..ui import select_command
from ..utils import get_alias, get_all_executables


def _get_raw_command(known_args):
    if known_args.force_command:
        return [known_args.force_command]
    elif not os.environ.get('TB_HISTORY'):
        return known_args.command
    else:
        history = os.environ['TB_HISTORY'].split('\n')[::-1]
        alias = get_alias()
        executables = get_all_executables()
        for command in history:
            if len(command) >= const.TRANSPORT_LIMIT:
                # The alias hands us whole history lines or none, but this
                # arrives in an environment variable and a shell that is still
                # running an older alias definition can put anything in it.
                # Half of a command is not something to offer to run.
                continue
            # Imported here: `difflib` is a hundred kilobytes that only a
            # correction with history behind it ever reads.
            from difflib import SequenceMatcher

            diff = SequenceMatcher(a=alias, b=command).ratio()
            if diff < const.DIFF_WITH_ALIAS or command in executables:
                return [command]
    return []


def fix_command(known_args):
    """Fixes previous command. Used when `thebleep` called without arguments."""
    settings.init(known_args)
    with logs.debug_time('Total'):
        if settings.debug:
            # pprint drags in dataclasses and inspect, which is a lot to pay
            # for a line nobody sees unless they asked for it.
            from pprint import pformat

            from ..conf import redacted

            logs.debug(u'Run with settings: {}'.format(
                pformat(redacted(settings))))
        raw_command = _get_raw_command(known_args)

        try:
            command = types.Command.from_raw_script(raw_command)
        except EmptyCommand:
            logs.debug('Empty command, nothing to do')
            return

        corrected_commands = get_corrected_commands(command)
        selected_command, action = select_command(corrected_commands, command)

        if selected_command is None:
            sys.exit(1)
        elif action is const.ACTION_EDIT:
            selected_command.edit()
            # The shell alias reads this status and puts what is on stdout in
            # the line editor. Nothing has been run.
            from ..shells import shell

            hint = shell.edit_hint()
            if hint:
                logs.edit_hint(hint)
            sys.exit(const.EXIT_EDIT)
        else:
            selected_command.run(command)
