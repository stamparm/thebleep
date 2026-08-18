import os
from subprocess import Popen, PIPE
from tempfile import gettempdir
from uuid import uuid4
from ..conf import settings
from ..const import (ARGUMENT_PLACEHOLDER, USER_COMMAND_MARK,
                     get_alias)
from ..utils import DEVNULL, memoize
from .generic import Generic, fit_transport


class Bash(Generic):
    friendly_name = 'Bash'

    def app_alias(self, alias_name):
        # It is VERY important to have the variables declared WITHIN the
        # function, and they are handed to `thebleep` in front of the command
        # rather than exported: they are how the shell describes itself to us,
        # and every other program the user runs afterwards has no business
        # seeing their alias list. A correction should leave nothing behind in
        # the shell it ran in.
        return '''
            function {name} () {{
                TB_SHELL_ALIASES=$(alias);
                TB_HISTORY=$(fc -ln -10);
                {fit_transport}
                TB_CMD=$(
                    TB_SHELL=bash TB_ALIAS={name} TB_SHELL_ALIASES="$TB_SHELL_ALIASES" TB_HISTORY="$TB_HISTORY" thebleep {argument_placeholder} "$@"
                ) && eval "$TB_CMD";
                {alter_history}
                unset TB_SHELL_ALIASES TB_HISTORY TB_CMD;
            }}
        '''.format(
            name=alias_name,
            argument_placeholder=ARGUMENT_PLACEHOLDER,
            fit_transport=fit_transport(),
            alter_history=('test -n "$TB_CMD" && history -s "$TB_CMD";'
                           if settings.alter_history else ''))

    def instant_mode_alias(self, alias_name):
        if os.environ.get('THEBLEEP_INSTANT_MODE', '').lower() == 'true':
            mark = USER_COMMAND_MARK + '\b' * len(USER_COMMAND_MARK)
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
                rm {log};
                exit
            '''.format(log=log_path)

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
        if os.path.join(os.path.expanduser('~'), '.bashrc'):
            config = '~/.bashrc'
        elif os.path.join(os.path.expanduser('~'), '.bash_profile'):
            config = '~/.bash_profile'
        else:
            config = 'bash config'

        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path=config,
            reload=u'source {}'.format(config))

    def _get_version(self):
        """Returns the version of the current shell"""
        proc = Popen(['bash', '-c', 'echo $BASH_VERSION'],
                     stdout=PIPE, stderr=DEVNULL)
        return proc.stdout.read().decode('utf-8').strip()
