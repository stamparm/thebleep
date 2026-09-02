from time import time
import os
from ..conf import settings
from ..const import (ARGUMENT_PLACEHOLDER, EXIT_EDIT, USER_COMMAND_MARK,
                     get_alias)
from ..utils import memoize, tool_output
from .generic import Generic, fit_transport, instant_log_path


class Zsh(Generic):
    friendly_name = 'ZSH'

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv(['zsh', '-c', script])

    def app_alias(self, alias_name):
        # It is VERY important to have the variables declared WITHIN the
        # function, and they are handed to `thebleep` in front of the command
        # rather than exported: they are how the shell describes itself to us,
        # and every other program the user runs afterwards has no business
        # seeing their alias list. A correction should leave nothing behind in
        # the shell it ran in.
        return '''
            {name} () {{
                TB_EXIT=${{TB_EXIT:-$?}};
                TB_SHELL_ALIASES=$(alias);
                TB_HISTORY="$(fc -ln -10)";
                {fit_transport}
                TB_CMD=$(
                    TB_SHELL=zsh TB_ALIAS={name} TB_EXIT="$TB_EXIT" TB_CAN_EDIT=1 TB_SHELL_ALIASES="$TB_SHELL_ALIASES" TB_HISTORY="$TB_HISTORY" {command} {argument_placeholder} "$@"
                );
                TB_STATUS=$?;
                if [ "$TB_STATUS" -eq {exit_edit} ]; then
                    {edit_line}
                elif [ "$TB_STATUS" -eq 0 ]; then
                    eval "$TB_CMD";
                    {alter_history}
                fi;
                unset TB_SHELL_ALIASES TB_HISTORY TB_CMD TB_STATUS TB_EXIT;
            }}
        '''.format(
            name=alias_name,
            command=self._invocation(),
            argument_placeholder=ARGUMENT_PLACEHOLDER,
            fit_transport=fit_transport(),
            exit_edit=EXIT_EDIT,
            edit_line=self._edit_line(),
            alter_history=('test -n "$TB_CMD" && print -s "$TB_CMD";'
                           if settings.alter_history else ''))

    def can_edit_buffer(self):
        return True

    def inline_binding(self):
        """Bind Esc Esc to a command-only correction in ZLE.

        The alias list is part of the shell context: an inline command can use
        a name that is not an executable, just like a command that has already
        run. Keep the transport local to the callback so it cannot leak into
        the user's next command.

        """
        return '''
{client}
__thebleep_inline() {{
    local TB_SHELL_ALIASES TB_HISTORY
    TB_SHELL_ALIASES=$(alias)
    TB_HISTORY=
    {fit_transport}
    if __thebleep_fixed "$BUFFER"; then
        BUFFER=$REPLY
        CURSOR=${{#BUFFER}}
    fi
    zle redisplay
}}
zle -N __thebleep_inline
bindkey '\\e\\e' __thebleep_inline
'''.format(fit_transport=fit_transport(), client=self._warm_client())

    def _warm_client(self):
        """A function that asks the warm server first, when that is on.

        `__thebleep_fixed BUFFER` sets `REPLY` to the correction and returns 0,
        or returns 1 for none. With `warm_server` on and `zsh/net/socket`
        loadable, the socket is tried before Python is started; a socket that
        is not there yet starts the server in the background for next time and
        falls through to the ordinary call this time.

        """
        from ..conf import settings

        direct = '''
    local fixed
    fixed=$(TB_SHELL=zsh TB_SHELL_ALIASES="$TB_SHELL_ALIASES" TB_HISTORY="$TB_HISTORY" {command} --inline --command "$1" 2>/dev/null)
    if [[ $? -eq 0 && -n $fixed ]]; then
        REPLY=$fixed
        return 0
    fi
    return 1'''.format(command=self._invocation())
        if not settings.warm_server:
            return '__thebleep_fixed() {' + direct + '\n}'

        from ..serve import socket_path

        return '''__thebleep_json() {{
    local s=$1
    s=${{s//\\\\/\\\\\\\\}}
    s=${{s//\\"/\\\\\\"}}
    s=${{s//$'\\n'/\\\\n}}
    s=${{s//$'\\r'/\\\\r}}
    s=${{s//$'\\t'/\\\\t}}
    REPLY=$s
}}
__thebleep_fixed() {{
    local sock={sock} fd answer
    if [[ -S $sock ]] && zmodload zsh/net/socket 2>/dev/null && zsocket $sock 2>/dev/null; then
        fd=$REPLY
        __thebleep_json "$1"; local script=$REPLY
        __thebleep_json "$TB_SHELL_ALIASES"; local aliases=$REPLY
        print -r -- "{{\\"script\\": \\"$script\\", \\"aliases\\": \\"$aliases\\"}}" >&$fd
        IFS= read -r answer <&$fd
        REPLY=$(cat <&$fd)
        exec {{fd}}>&-
        [[ $answer == ok && -n $REPLY ]] && return 0
        [[ $answer == none ]] && return 1
    elif [[ ! -S $sock ]]; then
        (TB_SHELL=zsh {command} --serve </dev/null >/dev/null 2>&1 &)
    fi{direct}
}}'''.format(sock=self.quote(socket_path('zsh')), command=self._invocation(),
             direct=direct)

    def ambient_binding(self):
        """Correct a misspelled program before it runs, on return.

        `accept-line` is wrapped: when the first word of the line is not a
        command, function, alias, builtin or reserved word -- `whence -w`
        says `none` -- the line is offered to The Bleep as a command-only
        correction, and if one comes back it replaces the buffer with a
        message underneath, so that return runs the corrected line and
        nothing has run yet. Any other line is accepted exactly as before,
        by whatever `accept-line` was bound to before this, so another
        plugin's wrapper is not lost.

        """
        return '''
if [[ ${{widgets[accept-line]}} == user:* ]]; then
    zle -A accept-line __thebleep_previous_accept_line
fi
{client}
__thebleep_ambient_accept_line() {{
    local first fixed TB_SHELL_ALIASES TB_HISTORY
    first=${{${{(z)BUFFER}}[1]}}
    if [[ -n $BUFFER && -n $first && $first != *[/=\\$\\'\\"\\`]* && "$(whence -w -- "$first" 2>/dev/null)" == *": none" ]]; then
        TB_SHELL_ALIASES=$(alias)
        TB_HISTORY=
        {fit_transport}
        if __thebleep_fixed "$BUFFER" && [[ $REPLY != $BUFFER ]]; then
            fixed=$REPLY
            zle -M "bleep: $first is not a command; return runs \\`$fixed\\`, ctrl+_ puts yours back"
            BUFFER=$fixed
            CURSOR=${{#BUFFER}}
            return 0
        fi
    fi
    if (( ${{+widgets[__thebleep_previous_accept_line]}} )); then
        zle __thebleep_previous_accept_line
    else
        zle .accept-line
    fi
}}
zle -N accept-line __thebleep_ambient_accept_line
'''.format(fit_transport=fit_transport(), client=self._warm_client())

    def _edit_line(self):
        """`print -z` is zsh's own answer to this, and has been for decades.

        It pushes the text onto the editor buffer stack, and the next prompt
        comes up with it already in the line editor -- the real ZLE, with the
        user's own keymap, at the real prompt. Nothing is typed at the terminal
        and nothing runs until they press return themselves.

        `-r` because `print` would otherwise read backslash escapes in a
        command that is meant to keep them.

        """
        return 'print -z -r -- "$TB_CMD";'

    def supports_instant_mode(self):
        return True

    def instant_mode_alias(self, alias_name):
        if os.environ.get('THEBLEEP_INSTANT_MODE', '').lower() == 'true':
            # The mark in `PS1`, and the semantic prompt marks from zsh's own
            # hooks: `preexec` prints `C` as the command is about to run,
            # `precmd` prints `D` with its status and `A` for the next
            # prompt. A theme that rebuilds `PS1` leaves the hooks alone.
            mark = ('%{' +
                    USER_COMMAND_MARK + '\b' * len(USER_COMMAND_MARK)
                    + '%}')
            return '''
                export PS1="{user_command_mark}$PS1";
                autoload -Uz add-zsh-hook;
                __thebleep_preexec() {{ printf '\\033]133;C\\007'; }};
                __thebleep_precmd() {{ printf '\\033]133;D;%s\\007\\033]133;A\\007' "$?"; }};
                add-zsh-hook preexec __thebleep_preexec;
                add-zsh-hook precmd __thebleep_precmd;
                {app_alias}
            '''.format(user_command_mark=mark,
                       app_alias=self.app_alias(alias_name))
        else:
            # The recording is removed by a trap and not by the line after the
            # logger: closing the terminal sends this shell a HUP and it never
            # reaches that line, which used to leave a megabyte of everything
            # that scrolled past sitting in /tmp until somebody noticed.
            log_path = self.quote(instant_log_path())
            return '''
                export THEBLEEP_INSTANT_MODE=True;
                export THEBLEEP_OUTPUT_LOG={log};
                trap 'rm -f {log}' EXIT HUP INT TERM;
                {command} --shell-logger {log};
                exit
            '''.format(log=log_path, command=self._invocation())

    def _parse_alias(self, alias):
        name, value = alias.split('=', 1)
        if len(value) > 1 and (value[0] == value[-1] == '"'
                               or value[0] == value[-1] == "'"):
            value = value[1:-1]
        return name, value

    @memoize
    def get_aliases(self):
        raw_aliases = os.environ.get('TB_SHELL_ALIASES', '').split('\n')
        return dict(self._parse_alias(alias)
                    for alias in raw_aliases if alias and '=' in alias)

    def _get_history_file_name(self):
        return os.environ.get("HISTFILE",
                              os.path.expanduser('~/.zsh_history'))

    def _get_history_line(self, command_script):
        return u': {}:0;{}\n'.format(int(time()), command_script)

    def _script_from_history(self, line):
        if ';' in line:
            return line.split(';', 1)[1]
        else:
            return ''

    def how_to_configure(self):
        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path='~/.zshrc',
            reload='source ~/.zshrc')

    def _get_version(self):
        """Returns the version of the current shell"""
        return tool_output(['zsh', '-c', 'echo $ZSH_VERSION']).strip()
