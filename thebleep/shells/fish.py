from time import time
import os
import sys
from .. import logs
from ..conf import settings
from ..const import ARGUMENT_PLACEHOLDER, EXIT_EDIT, TRANSPORT_LIMIT, \
    USER_COMMAND_MARK, get_alias
from ..utils import cache, tool_lines, tool_output
from .generic import Generic, instant_log_path


@cache('~/.config/fish/config.fish', '~/.config/fish/functions')
def _get_functions(overridden):
    # Through `tool_lines`, which is where the timeout is. `fish -ic` starts
    # an *interactive* fish, so it reads the user's `config.fish` -- and this is
    # on the hot path of every fish correction. A config that waits for
    # something (a prompt, a slow network mount, a version manager warming up)
    # used to be a correction that never came back.
    #
    # It is also where the decoding is: a non-UTF-8 locale can put a byte in a
    # function name that strict decoding raises on, uncaught.
    functions = [line.strip()
                 for line in tool_lines(['fish', '-ic', 'functions'])
                 if line.strip()]
    return {func: func for func in functions if func not in overridden}


@cache('~/.config/fish/config.fish')
def _get_aliases(overridden):
    return _parse_aliases(tool_lines(['fish', '-ic', 'alias']), overridden)


def _parse_aliases(lines, overridden):
    aliases = {}
    for alias in lines:
        for separator in (' ', '='):
            split_alias = alias.replace('alias ', '', 1).split(separator, 1)
            if len(split_alias) == 2:
                name, value = split_alias
                break
        else:
            continue
        if name not in overridden:
            aliases[name] = value
    return aliases


class Fish(Generic):
    friendly_name = 'Fish Shell'

    def replay_argv(self, script):
        """See `Generic.replay_argv`. fish's syntax is its own throughout --
        `set`, `and`, no `$?` -- so `sh` running a fish command line is not
        running the same command at all."""
        return self._posix_replay_argv(['fish', '-c', script])

    def supports_instant_mode(self):
        return True

    def instant_mode_alias(self, alias_name):
        if os.environ.get('THEBLEEP_INSTANT_MODE', '').lower() == 'true':
            # Fish prompts are functions rather than PS1. Copy the user's
            # prompt once, then put the same zero-width marker in front of it
            # that the recorder already understands for bash and zsh.
            # Backslashes are literal in a fish single-quoted string, so use a
            # double-quoted printf format and let printf turn them into real
            # backspaces. Putting them directly in the quote leaves them as
            # the two visible characters `\\b` and the reader cannot find a
            # mark.
            mark = '"{}"'.format(
                USER_COMMAND_MARK + r'\b' * len(USER_COMMAND_MARK))
            return '''
set -g __thebleep_prompt_mark (printf {mark})
set -gx PS1 $__thebleep_prompt_mark
if not functions -q __thebleep_original_prompt
    if functions -q fish_prompt
        functions --copy fish_prompt __thebleep_original_prompt
    else
        function __thebleep_original_prompt
            printf '> '
        end
    end
end
function fish_prompt
    printf '%s' $__thebleep_prompt_mark
    __thebleep_original_prompt
end
if test (string split . -- $FISH_VERSION)[1] -lt 4
    function __thebleep_preexec --on-event fish_preexec
        printf '\\e]133;C\\a'
    end
    function __thebleep_postexec --on-event fish_postexec
        printf '\\e]133;D;%s\\a' $status
    end
    function __thebleep_prompt_start --on-event fish_prompt
        printf '\\e]133;A\\a'
    end
end
{app_alias}
'''.format(mark=mark, app_alias=self.app_alias(alias_name))

        log_path = self.quote(instant_log_path())
        return '''
set -gx THEBLEEP_INSTANT_MODE True
set -gx THEBLEEP_OUTPUT_LOG {log}
function __thebleep_cleanup --on-event fish_exit
    command rm -f -- {log}
end
env SHELL=fish {command} --shell-logger {log}
exit
'''.format(log=log_path, command=self._invocation())

    def _get_overridden_aliases(self):
        overridden = os.environ.get('THEBLEEP_OVERRIDDEN_ALIASES',
                                    os.environ.get('TB_OVERRIDDEN_ALIASES', ''))
        default = {'cd', 'grep', 'ls', 'man', 'open'}
        for alias in overridden.split(','):
            default.add(alias.strip())
        return sorted(default)

    def app_alias(self, alias_name):
        if settings.alter_history:
            alter_history = ('    builtin history delete --exact'
                             ' --case-sensitive -- $broken_command\n'
                             '    builtin history merge\n')
        else:
            alter_history = ''
        # It is VERY important to have the variables declared WITHIN the alias
        #
        # The status is taken from `$pipestatus`, not `$status`: the correction
        # arrives through a pipe into `read`, so `$status` is the reader's and
        # says nothing about whether the user asked to edit.
        return ('function {0} -d "Correct your previous console command"\n'
                # Before anything else, or it is the status of whatever this
                # function did first rather than of the command being
                # corrected. And `$TB_EXIT` wins when the loader stub set it:
                # the stub's own `| source` replaces `$status`, so on the first
                # correction in a shell this saw the stub's zero instead of the
                # failing command's status.
                '  set -l tb_exit $status\n'
                '  if set -q TB_EXIT\n'
                '    set tb_exit $TB_EXIT\n'
                '  end\n'
                '  set -l broken_command $history[1]\n'
                '  set -l shell_aliases (alias | string collect)\n'
                '  if test (string length -- "$shell_aliases") -gt {limit}\n'
                '    set shell_aliases\n'
                '  end\n'
                '  env TB_SHELL=fish TB_ALIAS={0} TB_CAN_EDIT=1'
                ' TB_EXIT=$tb_exit'
                ' TB_SHELL_ALIASES="$shell_aliases"'
                ' {5} $broken_command {2} $argv | read -l fixed_command\n'
                '  set -l tb_status $pipestatus[1]\n'
                '  if test $tb_status -eq {3}\n'
                '    {4}\n'
                '  else if [ "$fixed_command" != "" ]\n'
                '    eval $fixed_command\n{1}'
                '  end\n'
                'end').format(alias_name, alter_history, ARGUMENT_PLACEHOLDER,
                              EXIT_EDIT, self._edit_line(),
                              self._invocation(), limit=TRANSPORT_LIMIT)

    def can_edit_buffer(self):
        return True

    def inline_binding(self):
        """Bind Esc Esc to a command-only correction in Fish."""
        return '''
function __thebleep_inline
    set -l shell_aliases (alias | string collect)
    if test (string length -- "$shell_aliases") -gt {limit}
        set shell_aliases
    end
    set -l fixed (env TB_SHELL=fish TB_SHELL_ALIASES="$shell_aliases" {command} --inline --command (commandline) | string collect)
    if test -n "$fixed"
        commandline --replace -- $fixed
    end
end
bind \\e\\e __thebleep_inline
'''.format(command=self._invocation(), limit=TRANSPORT_LIMIT)

    def ambient_binding(self):
        """Correct a misspelled program before it runs, on return.

        Return is bound to a function that looks at the first word of the
        line: when `type -q` knows nothing by that name, the line is offered
        to The Bleep as a command-only correction, and a fix replaces the
        buffer and repaints, so that return runs the corrected line. Anything
        else is `commandline -f execute`, which is what return did before.

        """
        return '''
function __thebleep_ambient_execute
    set -l buffer (commandline | string collect)
    set -l first (string split -m1 ' ' -- (string trim -l -- "$buffer"))[1]
    if test -n "$first"; and not string match -qr '[/=$\\'"`]' -- "$first"; and not type -q -- "$first"
        set -l shell_aliases (alias | string collect)
        if test (string length -- "$shell_aliases") -gt {limit}
            set shell_aliases
        end
        set -l fixed (env TB_SHELL=fish TB_SHELL_ALIASES="$shell_aliases" {command} --inline --command "$buffer" 2>/dev/null | string collect)
        if test -n "$fixed"; and test "$fixed" != "$buffer"
            printf '\\nbleep: %s is not a command; return runs `%s`\\n' "$first" "$fixed" >&2
            commandline -r -- $fixed
            commandline -f repaint
            return
        end
    end
    commandline -f execute
end
bind \\r __thebleep_ambient_execute
bind \\n __thebleep_ambient_execute
if bind -M insert >/dev/null 2>&1
    bind -M insert \\r __thebleep_ambient_execute
    bind -M insert \\n __thebleep_ambient_execute
end
'''.format(command=self._invocation(), limit=TRANSPORT_LIMIT)

    def _edit_line(self):
        """`commandline -r` writes fish's own line editor.

        Fish is one of the shells that will simply do this: the correction is
        in the buffer at the next prompt, with the cursor at the end of it, and
        nothing runs until the user presses return.

        """
        return 'commandline --replace -- $fixed_command'

    def app_alias_loader(self, alias_name):
        # `$status` first, and handed to the real function explicitly: the
        # `| source` below is a command of its own and replaces it, so the real
        # function's own `set -l tb_exit $status` saw a zero on the first
        # correction in a shell and took a failed command for a successful one.
        return ('function {name} -d "Correct your previous console command"\n'
                '  set -l tb_exit $status\n'
                '  functions -e {name}\n'
                '  env TB_SHELL=fish {command} --alias {name} | source\n'
                '  TB_EXIT=$tb_exit {name} $argv\n'
                'end').format(name=alias_name, command=self._invocation())

    def get_aliases(self):
        overridden = self._get_overridden_aliases()
        functions = _get_functions(overridden)
        transported = os.environ.get('TB_SHELL_ALIASES')
        raw_aliases = (_parse_aliases(transported.splitlines(), overridden)
                       if transported is not None
                       else _get_aliases(overridden))
        functions.update(raw_aliases)
        return functions

    def _expand_aliases(self, command_script):
        aliases = self.get_aliases()
        binary = command_script.split(' ')[0]
        if binary in aliases and aliases[binary] != binary:
            return command_script.replace(binary, aliases[binary], 1)
        elif binary in aliases:
            return u'fish -ic "{}"'.format(command_script.replace('"', r'\"'))
        else:
            return command_script

    def _get_history_file_name(self):
        # Fish keeps the history in the XDG data dir, the session name comes
        # from `$fish_history` and defaults to `fish`.
        session = os.environ.get('fish_history') or 'fish'
        data_home = os.environ.get('XDG_DATA_HOME') or '~/.local/share'
        history_file_name = os.path.join(
            os.path.expanduser(data_home), 'fish',
            u'{}_history'.format(session))

        if os.path.isfile(history_file_name):
            return history_file_name

        # Fish before 2.3 used to keep it next to the config:
        legacy_file_name = os.path.expanduser('~/.config/fish/fish_history')
        if os.path.isfile(legacy_file_name):
            return legacy_file_name

        return history_file_name

    def _get_history_line(self, command_script):
        return u'- cmd: {}\n   when: {}\n'.format(command_script, int(time()))

    def _script_from_history(self, line):
        if '- cmd: ' in line:
            return line.split('- cmd: ', 1)[1]
        else:
            return ''

    def and_(self, *commands):
        return u'; and '.join(commands)

    def put_on_path(self, directory):
        # `set -gx`, not `fish_add_path`: the latter writes a universal
        # variable that outlives the shell, and a correction has no business
        # changing anything past the session it runs in.
        return u'set -gx PATH {} $PATH'.format(self.quote(directory))

    def or_(self, *commands):
        return u'; or '.join(commands)

    def how_to_configure(self):
        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path='~/.config/fish/config.fish',
            reload='fish')

    def _get_version(self):
        """Returns the version of the current shell"""
        words = tool_output(['fish', '--version']).split()
        return words[-1] if words else ''

    def put_to_history(self, command):
        try:
            return self._put_to_history(command)
        except IOError:
            logs.exception("Can't update history", sys.exc_info())

    def _put_to_history(self, command_script):
        """Puts command script to shell history."""
        history_file_name = self._get_history_file_name()
        if os.path.isfile(history_file_name):
            with open(history_file_name, 'a') as history:
                entry = self._get_history_line(command_script)
                history.write(entry)
