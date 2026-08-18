from time import time
import os
from subprocess import Popen, PIPE
from tempfile import gettempdir
from uuid import uuid4
from ..conf import settings
from ..const import (ARGUMENT_PLACEHOLDER, USER_COMMAND_MARK,
                     get_alias)
from ..utils import DEVNULL, memoize
from .generic import Generic


class Zsh(Generic):
    friendly_name = 'ZSH'

    def app_alias(self, alias_name):
        # It is VERY important to have the variables declared WITHIN the function
        return '''
            {name} () {{
                TB_PYTHONIOENCODING=${{PYTHONIOENCODING:-}};
                export TB_SHELL=zsh;
                export TB_ALIAS={name};
                TB_SHELL_ALIASES=$(alias);
                export TB_SHELL_ALIASES;
                TB_HISTORY="$(fc -ln -10)";
                export TB_HISTORY;
                export PYTHONIOENCODING=utf-8;
                TB_CMD=$(
                    thebleep {argument_placeholder} $@
                ) && eval $TB_CMD;
                unset TB_HISTORY;
                export PYTHONIOENCODING=$TB_PYTHONIOENCODING;
                {alter_history}
            }}
        '''.format(
            name=alias_name,
            argument_placeholder=ARGUMENT_PLACEHOLDER,
            alter_history=('test -n "$TB_CMD" && print -s $TB_CMD'
                           if settings.alter_history else ''))

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
            log_path = os.path.join(
                gettempdir(), 'thebleep-script-log-{}'.format(uuid4().hex))
            return '''
                export THEBLEEP_INSTANT_MODE=True;
                export THEBLEEP_OUTPUT_LOG={log};
                thebleep --shell-logger {log};
                rm -f {log};
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
        proc = Popen(['zsh', '-c', 'echo $ZSH_VERSION'],
                     stdout=PIPE, stderr=DEVNULL)
        return proc.stdout.read().decode('utf-8').strip()
