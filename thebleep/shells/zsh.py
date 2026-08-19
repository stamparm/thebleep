from time import time
import os
from ..conf import settings
from ..const import (ARGUMENT_PLACEHOLDER, EXIT_EDIT, USER_COMMAND_MARK,
                     get_alias)
from ..utils import DEVNULL, load_subprocess, memoize
from .generic import Generic, fit_transport, instant_log_path


# Bound the first time a process is started here; see `utils.load_subprocess`.
Popen = None
PIPE = None


class Zsh(Generic):
    friendly_name = 'ZSH'

    def app_alias(self, alias_name):
        # It is VERY important to have the variables declared WITHIN the
        # function, and they are handed to `thebleep` in front of the command
        # rather than exported: they are how the shell describes itself to us,
        # and every other program the user runs afterwards has no business
        # seeing their alias list. A correction should leave nothing behind in
        # the shell it ran in.
        return '''
            {name} () {{
                TB_SHELL_ALIASES=$(alias);
                TB_HISTORY="$(fc -ln -10)";
                {fit_transport}
                TB_CMD=$(
                    TB_SHELL=zsh TB_ALIAS={name} TB_CAN_EDIT=1 TB_SHELL_ALIASES="$TB_SHELL_ALIASES" TB_HISTORY="$TB_HISTORY" thebleep {argument_placeholder} "$@"
                );
                TB_STATUS=$?;
                if [ "$TB_STATUS" -eq {exit_edit} ]; then
                    {edit_line}
                elif [ "$TB_STATUS" -eq 0 ]; then
                    eval "$TB_CMD";
                    {alter_history}
                fi;
                unset TB_SHELL_ALIASES TB_HISTORY TB_CMD TB_STATUS;
            }}
        '''.format(
            name=alias_name,
            argument_placeholder=ARGUMENT_PLACEHOLDER,
            fit_transport=fit_transport(),
            exit_edit=EXIT_EDIT,
            edit_line=self._edit_line(),
            alter_history=('test -n "$TB_CMD" && print -s "$TB_CMD";'
                           if settings.alter_history else ''))

    def can_edit_buffer(self):
        return True

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
            mark = ('%{' +
                    USER_COMMAND_MARK + '\b' * len(USER_COMMAND_MARK)
                    + '%}')
            return '''
                export PS1="{user_command_mark}$PS1";
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
                thebleep --shell-logger {log};
                exit
            '''.format(log=log_path)

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
        Popen, PIPE = load_subprocess(globals())
        proc = Popen(['zsh', '-c', 'echo $ZSH_VERSION'],
                     stdout=PIPE, stderr=DEVNULL)
        return proc.stdout.read().decode('utf-8').strip()
