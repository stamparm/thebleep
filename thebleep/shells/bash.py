import os
import sys
from ..conf import settings
from ..const import (ARGUMENT_PLACEHOLDER, EXIT_EDIT, USER_COMMAND_MARK,
                     get_alias)
from ..utils import memoize, tool_output
from .generic import Generic, fit_transport, instant_log_path


class Bash(Generic):
    friendly_name = 'Bash'

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv(['bash', '-c', script])

    def app_alias(self, alias_name):
        # It is VERY important to have the variables declared WITHIN the
        # function, and they are handed to `thebleep` in front of the command
        # rather than exported: they are how the shell describes itself to us,
        # and every other program the user runs afterwards has no business
        # seeing their alias list. A correction should leave nothing behind in
        # the shell it ran in.
        return '''
            function {name} () {{
                TB_EXIT=${{TB_EXIT:-$?}};
                TB_SHELL_ALIASES=$(alias);
                TB_HISTORY=$(fc -ln -10);
                {fit_transport}
                TB_CAN_EDIT=; [ "${{BASH_VERSINFO[0]:-0}}" -ge 4 ] && TB_CAN_EDIT=1;
                TB_CMD=$(
                    TB_SHELL=bash TB_ALIAS={name} TB_EXIT="$TB_EXIT" TB_CAN_EDIT="$TB_CAN_EDIT" TB_SHELL_ALIASES="$TB_SHELL_ALIASES" TB_HISTORY="$TB_HISTORY" {command} {argument_placeholder} "$@"
                );
                TB_STATUS=$?;
                if [ "$TB_STATUS" -eq {exit_edit} ]; then
                    {edit_line}
                elif [ "$TB_STATUS" -eq 0 ]; then
                    eval "$TB_CMD";
                    {alter_history}
                fi;
                unset TB_SHELL_ALIASES TB_HISTORY TB_CMD TB_STATUS TB_CAN_EDIT TB_EXIT;
            }}
        '''.format(
            name=alias_name,
            command=self._invocation(),
            argument_placeholder=ARGUMENT_PLACEHOLDER,
            fit_transport=fit_transport(),
            exit_edit=EXIT_EDIT,
            edit_line=self._edit_line(),
            alter_history=('test -n "$TB_CMD" && history -s "$TB_CMD";'
                           if settings.alter_history else ''))

    def can_edit_buffer(self):
        """Readline, from bash 4.0 -- which is what `-i` below needs.

        The alias works out the version for itself and only offers editing when
        the shell it is running in can do it, so a macOS system bash (still
        3.2) is never offered something it would fail at.

        """
        return True

    def inline_binding(self):
        """Bind Esc Esc to a command-only correction in readline.

        The alias list is part of the shell context: an inline command can use
        a name that is not an executable, just like a command that has already
        run. Keep the transport local to the callback so it cannot leak into
        the user's next command.

        """
        return '''
if [ "${{BASH_VERSINFO[0]:-0}}" -ge 4 ]; then
    __thebleep_inline() {{
        local fixed TB_SHELL_ALIASES TB_HISTORY
        TB_SHELL_ALIASES=$(alias)
        TB_HISTORY=
        {fit_transport}
        fixed=$(TB_SHELL=bash TB_SHELL_ALIASES="$TB_SHELL_ALIASES" TB_HISTORY="$TB_HISTORY" {command} --inline --command "$READLINE_LINE")
        if [ "$?" -eq 0 ] && [ -n "$fixed" ]; then
            READLINE_LINE="$fixed"
            READLINE_POINT=${{#READLINE_LINE}}
        fi
    }}
    bind -x '"\\e\\e":__thebleep_inline'
fi
'''.format(command=self._invocation(), fit_transport=fit_transport())

    def ambient_binding(self):
        """Correct a misspelled program without `bleep` being typed.

        Bash runs `command_not_found_handle` in a subshell, so the handler
        cannot put anything in the parent's line editor. It hands the fix to
        the parent through a file of its own -- `$$` is the parent's pid even
        in the subshell, and the file lives in The Bleep's cache directory,
        created with a private mode -- and a `PROMPT_COMMAND` hook picks it
        up before the next prompt and opens it in readline with `read -e -i`,
        exactly as tab does for an ordinary correction. Nothing runs until
        return is pressed on a line that is already the corrected command.

        The handler prints bash's own message first, because bash prints
        nothing itself once a handler is defined.

        """
        return '''
if [ "${{BASH_VERSINFO[0]:-0}}" -ge 4 ]; then
    __thebleep_ambient_file() {{ printf '%s/ambient-%s' {cache} "$$"; }}
    command_not_found_handle() {{
        local fixed file TB_SHELL_ALIASES TB_HISTORY
        printf 'bash: %s: command not found\\n' "$1" >&2
        TB_SHELL_ALIASES=$(alias)
        TB_HISTORY=
        {fit_transport}
        fixed=$(TB_SHELL=bash TB_SHELL_ALIASES="$TB_SHELL_ALIASES" TB_HISTORY="$TB_HISTORY" {command} --inline --command "$*" 2>/dev/null)
        if [ "$?" -eq 0 ] && [ -n "$fixed" ]; then
            file=$(__thebleep_ambient_file)
            mkdir -p -m 700 -- "${{file%/*}}" 2>/dev/null
            (umask 077; printf '%s' "$fixed" > "$file")
        fi
        return 127
    }}
    __thebleep_ambient() {{
        local file fixed TB_PROMPT TB_EDIT
        file=$(__thebleep_ambient_file)
        [ -f "$file" ] || return 0
        fixed=$(<"$file")
        rm -f -- "$file"
        [ -n "$fixed" ] || return 0
        TB_PROMPT='> '
        eval 'TB_PROMPT="${{PS1@P}}"' 2>/dev/null
        IFS= read -r -e -i "$fixed" -p "$TB_PROMPT" TB_EDIT && [ -n "$TB_EDIT" ] && {{ {history}eval "$TB_EDIT"; }}
    }}
    if [[ "$(declare -p PROMPT_COMMAND 2>/dev/null)" == "declare -a"* ]]; then
        PROMPT_COMMAND+=(__thebleep_ambient)
    else
        PROMPT_COMMAND="__thebleep_ambient${{PROMPT_COMMAND:+;$PROMPT_COMMAND}}"
    fi
fi
'''.format(command=self._invocation(), fit_transport=fit_transport(),
           cache=self.quote(self._ambient_directory()),
           history='history -s "$TB_EDIT"; ' if settings.alter_history else '')

    def _edit_line(self):
        """Reopens the correction in readline for the user to finish.

        Bash has no way to write the *next* prompt's buffer the way zsh's
        `print -z` does, and the one that would work everywhere is pushing
        characters into the terminal with `TIOCSTI`, which is not something to
        do to somebody's terminal. `read -e -i` is the supported alternative:
        the real readline, with the real keymap and the real history, on a line
        that already contains the correction.

        The prompt is the user's own, rendered by `${PS1@P}` -- bash 4.4 and
        later, and inside an `eval` so that a shell without it fails one
        statement rather than refusing to parse the whole function.

        """
        history = 'history -s "$TB_EDIT"; ' if settings.alter_history else ''
        return ("TB_PROMPT='> ';"
                " eval 'TB_PROMPT=\"${PS1@P}\"' 2>/dev/null;"
                ' IFS= read -r -e -i "$TB_CMD" -p "$TB_PROMPT" TB_EDIT'
                ' && [ -n "$TB_EDIT" ]'
                ' && { ' + history + 'eval "$TB_EDIT"; };'
                ' unset TB_PROMPT TB_EDIT;')

    def supports_instant_mode(self):
        return True

    def instant_mode_alias(self, alias_name):
        if os.environ.get('THEBLEEP_INSTANT_MODE', '').lower() == 'true':
            # Two ways of telling the recording where a command's output is.
            # The mark in `PS1` is the old one, and a prompt framework that
            # rebuilds `PS1` takes it away. The semantic prompt marks are the
            # new one: `PS0` is printed after a command is read and before it
            # runs (bash 4.4+), which is `C`; the first thing `PROMPT_COMMAND`
            # does is `D` with the status and `A` for the prompt to come.
            # Nothing a theme does to `PS1` touches either. No `\\[ \\]`
            # around the `PS0` mark: those are readline's, `PS0` never goes
            # through readline, and bash writes them out as `\\001`/`\\002`.
            mark = USER_COMMAND_MARK + '\b' * len(USER_COMMAND_MARK)
            return '''
                export PS1="{user_command_mark}$PS1";
                PS0="\\e]133;C\\a$PS0";
                __thebleep_precmd() {{ printf '\\033]133;D;%s\\007\\033]133;A\\007' "$?"; }};
                if [[ "$(declare -p PROMPT_COMMAND 2>/dev/null)" == "declare -a"* ]]; then
                    PROMPT_COMMAND=(__thebleep_precmd "${{PROMPT_COMMAND[@]}}");
                else
                    PROMPT_COMMAND="__thebleep_precmd${{PROMPT_COMMAND:+;$PROMPT_COMMAND}}";
                fi;
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
        name, value = alias.replace('alias ', '', 1).split('=', 1)
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
                              os.path.expanduser('~/.bash_history'))

    def _get_history_line(self, command_script):
        return u'{}\n'.format(command_script)

    def how_to_configure(self):
        # `os.path.join(...)` was the test here, and a joined path is a
        # non-empty string, so the first branch always won and `.bash_profile`
        # was never named -- on a machine that has one and no `.bashrc`, which
        # is the usual macOS shape, the advice was to edit a file that is not
        # there.
        #
        # With neither there, the answer has to be a file and not a description
        # of one: `bash config` was printed straight into the advice, which came
        # out as ``Run `thebleep --alias-loader >> bash config` `` -- a sentence
        # where a path belongs. The file to name is then the one bash would read
        # if it existed, which differs by platform: macOS's Terminal starts a
        # login shell, and a login shell reads `~/.bash_profile` and not
        # `~/.bashrc`. Appending to either creates it.
        home = os.path.expanduser('~')
        if os.path.exists(os.path.join(home, '.bashrc')):
            config = '~/.bashrc'
        elif os.path.exists(os.path.join(home, '.bash_profile')):
            config = '~/.bash_profile'
        elif sys.platform == 'darwin':
            config = '~/.bash_profile'
        else:
            config = '~/.bashrc'

        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path=config,
            reload=u'source {}'.format(config))

    def _get_version(self):
        """Returns the version of the current shell"""
        return tool_output(['bash', '-c', 'echo $BASH_VERSION']).strip()
