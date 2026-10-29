from time import time
import os
from ..conf import settings
from ..const import (ARGUMENT_PLACEHOLDER, EXIT_EDIT, USER_COMMAND_MARK,
                     get_alias)
from ..utils import memoize, tool_output
from .generic import Generic, fit_transport, instant_log_path


class Zsh(Generic):
    friendly_name = 'ZSH'

    def native_path(self, path):
        return self._msys_path(path)

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv(['zsh', '-f', '-c', script])

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
                    TB_STATUS=0;
                elif [ "$TB_STATUS" -eq 0 ]; then
                    eval "$TB_CMD";
                    TB_STATUS=$?;
                    {alter_history}
                fi;
                set -- "$TB_STATUS";
                unset TB_SHELL_ALIASES TB_HISTORY TB_CMD TB_STATUS TB_EXIT;
                return "$1";
            }}
        '''.format(
            name=alias_name,
            command=self._invocation(),
            argument_placeholder=ARGUMENT_PLACEHOLDER,
            fit_transport=fit_transport(),
            exit_edit=EXIT_EDIT,
            edit_line=self._edit_line(),
            alter_history=('test -n "$TB_CMD" && print -rs -- "$TB_CMD";'
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

        `__thebleep_fixed BUFFER known` asks the other question -- the first
        word is a command, is the word after it one the command has
        (`thebleep.ambient`)? -- and only of the socket: it is asked at
        every return of an ordinary line, and starting Python for each is
        not on. Without a socket it starts the server and says no.

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
    local sock={sock} fd answer known=false
    [[ $2 == known ]] && known=true
    if [[ -S $sock ]] && zmodload zsh/net/socket 2>/dev/null && zsocket $sock 2>/dev/null; then
        fd=$REPLY
        __thebleep_json "$1"; local script=$REPLY
        __thebleep_json "$TB_SHELL_ALIASES"; local aliases=$REPLY
        __thebleep_json "$PWD"; local cwd=$REPLY
        __thebleep_json "$PATH"; local tb_path=$REPLY
        print -r -- "{{\\"script\\": \\"$script\\", \\"aliases\\": \\"$aliases\\", \\"cwd\\": \\"$cwd\\", \\"path\\": \\"$tb_path\\", \\"known\\": $known}}" >&$fd
        IFS= read -r answer <&$fd
        REPLY=$(cat <&$fd)
        exec {{fd}}>&-
        [[ $answer == ok && -n $REPLY ]] && return 0
        [[ $answer == none ]] && return 1
    elif [[ ! -S $sock ]] || zmodload zsh/net/socket 2>/dev/null; then
        # No socket, or one nothing listens on: a server that was killed.
        (TB_SHELL=zsh {command} --serve </dev/null >/dev/null 2>&1 &)
    fi
    [[ $known == true ]] && return 1{direct}
}}'''.format(sock=self.quote(socket_path('zsh')), command=self._invocation(),
             direct=direct)

    def ambient_binding(self):
        """Correct a misspelled program before it runs, on return.

        `accept-line` is wrapped: when the first word of the line is not a
        command, function, alias, builtin or reserved word -- `whence -w`
        says `none` -- the line is offered to The Bleep as a command-only
        correction, and if one comes back it replaces the buffer with a
        message underneath, so that return runs the corrected line and
        nothing has run yet.

        When the first word *is* a command and a plain word follows it, on a
        line with no operator, quote, variable or path in it, the warm
        server is asked whether that word is one the command has
        (`thebleep.ambient`): `git satus` becomes `git status` the same way.
        Only the socket is asked -- this runs at nearly every return -- and
        the server answers from files, so a line it has no opinion on costs
        a few milliseconds and is accepted as it was.

        Any other line is accepted exactly as before, by whatever
        `accept-line` was bound to before this, so another plugin's wrapper
        is not lost.

        """
        return '''
if [[ ${{widgets[accept-line]}} == user:* ]]; then
    zle -A accept-line __thebleep_previous_accept_line
fi
{client}
__thebleep_ambient_accept_line() {{
    local first second fixed TB_SHELL_ALIASES TB_HISTORY
    local -a words
    words=(${{(z)BUFFER}})
    first=$words[1]
    second=$words[2]
    if [[ -n $__thebleep_answer && $BUFFER == $__thebleep_asked && $__thebleep_answer != $BUFFER ]]; then
        fixed=$__thebleep_answer
        __thebleep_answer=
        zle -M "bleep: $__thebleep_what; return runs \\`$fixed\\`, ctrl+_ puts yours back"
        BUFFER=$fixed
        CURSOR=${{#BUFFER}}
        return 0
    elif [[ -n $BUFFER && -n $first && $first != *[/=\\$\\'\\"\\`]* && "$(whence -w -- "$first" 2>/dev/null)" == *": none" ]]; then
        TB_SHELL_ALIASES=$(alias)
        TB_HISTORY=
        {fit_transport}
        if __thebleep_fixed "$BUFFER" && [[ $REPLY != "$BUFFER" ]]; then
            fixed=$REPLY
            zle -M "bleep: $first is not a command; return runs \\`$fixed\\`, ctrl+_ puts yours back"
            BUFFER=$fixed
            CURSOR=${{#BUFFER}}
            return 0
        fi
    elif [[ -n $second && $first == [A-Za-z0-9]* && $second == [A-Za-z0-9]* && $BUFFER != *[/=\\|\\;\\&\\<\\>\\(\\)\\{{\\}}\\$\\'\\"\\`\\\\]* && "$(whence -w -- "$first" 2>/dev/null)" == *": command" ]]; then
        TB_SHELL_ALIASES=
        TB_HISTORY=
        if __thebleep_fixed "$BUFFER" known && [[ $REPLY != "$BUFFER" ]]; then
            fixed=$REPLY
            zle -M "bleep: $second is not a $first command; return runs \\`$fixed\\`, ctrl+_ puts yours back"
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
{watch}'''.format(
            fit_transport=fit_transport(), client=self._warm_client(),
            watch=self._watch_while_typing())

    def _watch_while_typing(self):
        """Ask the warm server while the line is being typed.

        `zle-line-pre-redraw` runs after every keystroke. When the first
        word is finished and is nothing the shell knows -- the `commands`,
        `aliases`, `functions`, `builtins` and `reswords` hashes, no fork --
        or is a command with a plain word after it, the question is written
        to the socket and `zle -F` is told to call back when the answer is
        readable. The callback has no editor state of its own -- `BUFFER` is
        empty there -- so it hands the answer to a widget, which has. The
        answer, if it is for the line as it still stands, is kept and shown
        underneath; return then takes it without asking, so
        the correction costs nothing at the keystroke that matters. A
        keystroke that changes the line drops a pending question and a
        stale answer. Nothing is asked without a socket, beyond starting the
        server for next time: this runs at every keystroke, and Python is
        not started for one.

        """
        from ..conf import settings

        if not settings.warm_server:
            return ''

        from ..serve import socket_path

        return r'''typeset -g __thebleep_asked __thebleep_answer __thebleep_what __thebleep_fd __thebleep_aliases __thebleep_shown
__thebleep_cancel() {
    if [[ -n $__thebleep_fd ]]; then
        zle -F $__thebleep_fd 2>/dev/null
        exec {__thebleep_fd}>&-
        __thebleep_fd=
    fi
}
__thebleep_ask() {
    local sock=SOCK fd script aliases cwd tb_path known=false
    [[ $2 == known ]] && known=true
    __thebleep_cancel
    __thebleep_asked=$1
    __thebleep_answer=
    if [[ ! -S $sock ]]; then
        (TB_SHELL=zsh COMMAND --serve </dev/null >/dev/null 2>&1 &)
        return
    fi
    zmodload zsh/net/socket 2>/dev/null || return
    if ! zsocket $sock 2>/dev/null; then
        # A socket nothing listens on: a server that was killed.
        (TB_SHELL=zsh COMMAND --serve </dev/null >/dev/null 2>&1 &)
        return
    fi
    fd=$REPLY
    __thebleep_json "$1"; script=$REPLY
    __thebleep_json "$__thebleep_aliases"; aliases=$REPLY
    __thebleep_json "$PWD"; cwd=$REPLY
    __thebleep_json "$PATH"; tb_path=$REPLY
    print -r -- "{\"script\": \"$script\", \"aliases\": \"$aliases\", \"cwd\": \"$cwd\", \"path\": \"$tb_path\", \"known\": $known}" >&$fd
    __thebleep_fd=$fd
    zle -F $fd __thebleep_arrived
}
__thebleep_arrived() {
    local fd=$1 answer fixed
    zle -F $fd
    __thebleep_fd=
    if [[ $2 != err ]]; then
        IFS= read -r -t 1 answer <&$fd
        IFS= read -r -t 1 fixed <&$fd
    fi
    exec {fd}>&-
    # The editor's state is not in scope here, `BUFFER` included; a widget
    # called from here has it, which is how the answer is checked against
    # the line as it stands now.
    [[ $answer == ok && -n $fixed ]] && zle __thebleep_show -- "$fixed" "$__thebleep_asked"
}
__thebleep_show() {
    if [[ $BUFFER == $2 && $1 != $BUFFER ]]; then
        __thebleep_answer=$1
        __thebleep_shown=1
        zle -M "bleep: $__thebleep_what; return runs \`$1\`"
    fi
}
zle -N __thebleep_show
__thebleep_watch() {
    local first second
    local -a words
    words=(${(z)BUFFER})
    first=$words[1]
    second=$words[2]
    [[ $BUFFER == $__thebleep_asked ]] && return
    if [[ -n $first && $BUFFER == *[[:space:]]* && $first != *[/=\$\'\"\`]* ]] && ! (( $+commands[$first] + $+aliases[$first] + $+functions[$first] + $+builtins[$first] + $+reswords[$first] )); then
        [[ -z $__thebleep_aliases ]] && __thebleep_aliases=$(alias)
        __thebleep_what="$first is not a command"
        __thebleep_ask "$BUFFER"
    elif [[ -n $second && $first == [A-Za-z0-9]* && $second == [A-Za-z0-9]* && $BUFFER != *[/=\|\;\&\<\>\(\)\{\}\$\'\"\`\\]* ]] && (( $+commands[$first] )); then
        __thebleep_what="$second is not a $first command"
        __thebleep_ask "$BUFFER" known
    else
        __thebleep_cancel
        __thebleep_asked=
        __thebleep_answer=
    fi
    if [[ -n $__thebleep_shown && -z $__thebleep_answer ]]; then
        __thebleep_shown=
        zle -M ''
    fi
}
__thebleep_line_init() {
    __thebleep_asked=
    __thebleep_answer=
    __thebleep_aliases=
    __thebleep_shown=
}
autoload -Uz add-zle-hook-widget
add-zle-hook-widget line-pre-redraw __thebleep_watch
add-zle-hook-widget line-init __thebleep_line_init
add-zle-hook-widget line-finish __thebleep_cancel
'''.replace('SOCK', self.quote(socket_path('zsh'))).replace(
            'COMMAND', self._invocation())

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
