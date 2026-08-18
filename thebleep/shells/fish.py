from time import time
import os
import sys
from .. import logs
from ..conf import settings
from ..const import ARGUMENT_PLACEHOLDER, get_alias
from ..utils import DEVNULL, cache, load_subprocess
from .generic import Generic


# Bound the first time a process is started here; see `utils.load_subprocess`.
Popen = None
PIPE = None


@cache('~/.config/fish/config.fish', '~/.config/fish/functions')
def _get_functions(overridden):
    Popen, PIPE = load_subprocess(globals())
    proc = Popen(['fish', '-ic', 'functions'], stdout=PIPE, stderr=DEVNULL)
    functions = proc.stdout.read().decode('utf-8').strip().split('\n')
    return {func: func for func in functions if func not in overridden}


@cache('~/.config/fish/config.fish')
def _get_aliases(overridden):
    aliases = {}
    Popen, PIPE = load_subprocess(globals())
    proc = Popen(['fish', '-ic', 'alias'], stdout=PIPE, stderr=DEVNULL)
    alias_out = proc.stdout.read().decode('utf-8').strip()
    if not alias_out:
        return aliases
    for alias in alias_out.split('\n'):
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
        return ('function {0} -d "Correct your previous console command"\n'
                '  set -l broken_command $history[1]\n'
                '  env TB_SHELL=fish TB_ALIAS={0}'
                ' thebleep $broken_command {2} $argv | read -l fixed_command\n'
                '  if [ "$fixed_command" != "" ]\n'
                '    eval $fixed_command\n{1}'
                '  end\n'
                'end').format(alias_name, alter_history, ARGUMENT_PLACEHOLDER)

    def app_alias_loader(self, alias_name):
        return ('function {name} -d "Correct your previous console command"\n'
                '  functions -e {name}\n'
                '  env TB_SHELL=fish thebleep --alias {name} | source\n'
                '  {name} $argv\n'
                'end').format(name=alias_name)

    def get_aliases(self):
        overridden = self._get_overridden_aliases()
        functions = _get_functions(overridden)
        raw_aliases = _get_aliases(overridden)
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

    def or_(self, *commands):
        return u'; or '.join(commands)

    def how_to_configure(self):
        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path='~/.config/fish/config.fish',
            reload='fish')

    def _get_version(self):
        """Returns the version of the current shell"""
        Popen, PIPE = load_subprocess(globals())
        proc = Popen(['fish', '--version'], stdout=PIPE, stderr=DEVNULL)
        return proc.stdout.read().decode('utf-8').split()[-1]

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
