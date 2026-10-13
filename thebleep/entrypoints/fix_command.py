import os
import sys
from contextlib import contextmanager
from .. import logs, types, const
from ..conf import settings
from ..corrector import get_corrected_commands
from ..exceptions import EmptyCommand
from .. import failure_store
from ..ui import select_command
from ..utils import get_alias, get_all_executables


def _like_the_alias(command, alias, executables):
    """Whether `command` is the alias, or a slip of it, rather than a command
    to correct: `belep`, `bleeep`."""
    from difflib import SequenceMatcher

    word = command.split(' ', 1)[0] if command else ''
    return bool(word) and word not in executables and \
        SequenceMatcher(a=alias, b=word).ratio() >= const.DIFF_WITH_ALIAS


def _get_raw_command(known_args):
    if known_args.force_command:
        return [known_args.force_command]
    elif not os.environ.get('TB_HISTORY'):
        # fish hands over `$history[1]`, which is `belep` when that was the
        # alias mistyped a moment ago -- and `belep` came back as `beep`.
        # What was meant is the command before it, as the bash path below
        # already worked out.
        command = known_args.command
        alias = get_alias()
        if len(command or ()) == 1 and command[0] != alias \
                and _like_the_alias(command[0], alias, get_all_executables()):
            from ..shells import shell

            for line in reversed(shell.get_history()):
                if line and not _like_the_alias(
                        line, alias, get_all_executables()):
                    return [line]
        return command
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
                if _history_missed_it(command):
                    return []
                return [command]
    return []


def _history_missed_it(command):
    """Whether the command just run never reached the history.

    With `HISTCONTROL=ignorespace` (Ubuntu's default, as `ignoreboth`) a
    command typed after a space is not recorded, so the newest history line
    is the one *before* it -- and `bleep` offered to run that again. bash's
    `$_`, which the alias passes on, is the last argument of the command that
    really ran, history or not. When it is not the last word of the history
    line, the line is not that command. Only a plain line is judged: a
    redirection, a pipe, a variable or a glob can make the two differ for
    nothing.

    """
    if 'ignore' not in os.environ.get('TB_HISTCONTROL', ''):
        return False
    last_argument = os.environ.get('TB_LAST_ARG')
    if not last_argument or any(character in command
                                for character in '$`*?[{~\\\'"'):
        return False
    import re

    # The last simple command, and its words without the redirections: `$_`
    # for `echo prev > /tmp/prev.txt` is `prev`.
    segment = re.split(r'&&|\|\||[|;&]', command)[-1]
    words = []
    skip = False
    for word in segment.split():
        if skip:
            skip = False
            continue
        if re.match(r'^\d*(?:&>|>>|>|<)', word):
            skip = re.match(r'^\d*(?:&>|>>|>|<)&?$', word) is not None
            continue
        words.append(word)
    if not words or words[-1] == last_argument:
        return False
    logs.warn(u'The command you ran is not in your history -- it began with '
              u'a space, which HISTCONTROL={} leaves out -- so there is '
              u'nothing to correct.'.format(os.environ['TB_HISTCONTROL']))
    return True


@contextmanager
def _picked_failure(number):
    """Yields a stored command and temporarily restores its working directory."""
    entries = failure_store.load()
    if number == 0:
        failure_store.print_recent(entries)
        yield None
        return
    if number < 1 or number > len(entries):
        logs.failed('No recorded failure {}'.format(number))
        yield None
        return

    entry = entries[number - 1]
    try:
        previous = os.getcwd()
    except OSError:
        # A shell can remain in a directory that was removed underneath it.
        # There is no path to restore in that case, but selecting a saved
        # failure should still be able to use its recorded directory.
        previous = None
    try:
        try:
            os.chdir(entry['cwd'])
        except OSError:
            logs.warn('Could not restore {}; using {}'.format(
                entry['cwd'], previous))
        yield types.Command(entry['script'], entry['output'])
    finally:
        if previous is not None:
            try:
                os.chdir(previous)
            except OSError:
                logs.debug('Could not restore the original working directory')


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
        picked = getattr(known_args, 'pick', None)
        if type(picked) is not int:
            picked = None
        if picked is not None:
            with _picked_failure(picked) as command:
                if command is None:
                    return
                _fix_command(known_args, command)
            return

        raw_command = _get_raw_command(known_args)

        try:
            command = types.Command.from_raw_script(raw_command)
        except EmptyCommand:
            logs.debug('Empty command, nothing to do')
            if getattr(known_args, 'why', False):
                # Asked a question and given silence and a zero: say there was
                # nothing to explain, and fail like it.
                logs.warn('No previous command to explain; run it first, or '
                          'name one with --command.')
            # Nothing was corrected, which a `&&` after `bleep` should see.
            sys.exit(1)

        try:
            cwd = os.getcwd()
        except OSError:
            cwd = ''
        failure_store.record(command.script, command.output,
                             os.environ.get('TB_EXIT'), cwd,
                             os.environ.get('TB_SHELL'))
        _fix_command(known_args, command)


def _ask_the_explainer(command):
    """The user's own explainer, when the deterministic one had nothing."""
    from .. import explainer

    if explainer.configured() is None:
        return
    answer = explainer.ask(command.script, command.output,
                           os.environ.get('TB_EXIT'))
    if answer is None:
        logs.warn('{} gave no answer'.format(explainer.configured()))
        return
    print(explainer.heading())
    print(answer)


def _or_the_suggester(corrected_commands, command):
    """The rules' corrections, or -- when there are none and the user has
    named one -- what `suggest_command` offers, as one row saying so."""
    from itertools import chain

    corrected_commands = iter(corrected_commands)
    first = next(corrected_commands, None)
    if first is not None:
        return chain([first], corrected_commands)

    from .. import explainer

    # Not with `--yes` or `require_confirmation = False`: there the first row
    # runs unasked, and this one is somebody's model talking.
    if explainer.suggester() is None or not settings.require_confirmation:
        return iter(())
    from ..replay import previous_status

    offered = explainer.suggest(command.script, command.output,
                                previous_status())
    if offered is None:
        return iter(())
    return iter([types.CorrectedCommand(
        offered, None, 1, evidence=(u'from {}, which is not a deterministic '
                                    u'source'.format(explainer.suggester()),))])


def _fix_command(known_args, command):
    """Correct one already acquired command."""

    if getattr(known_args, 'why', False):
        from .. import diagnostics

        result = diagnostics.diagnose(command.script, command.output)
        print(diagnostics.format_human(result))
        if not result['diagnoses']:
            _ask_the_explainer(command)
        return

    corrected_commands = _or_the_suggester(get_corrected_commands(command),
                                           command)
    selected_command, action = select_command(corrected_commands, command)

    if selected_command is None:
        sys.exit(1)

    from .. import stats

    rule = getattr(selected_command, 'rule', None)
    stats.bump('edited' if action is const.ACTION_EDIT else 'accepted',
               rule=rule.name if rule is not None else None,
               before=command.script, after=selected_command.script)
    if action is const.ACTION_EDIT:
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
