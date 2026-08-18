from subprocess import Popen, PIPE
from ..const import get_alias
from ..utils import DEVNULL
from .generic import Generic, ShellConfiguration


class Powershell(Generic):
    friendly_name = 'PowerShell'

    def app_alias(self, alias_name):
        return 'function ' + alias_name + ' {\n' \
               '    $history = (Get-History -Count 1).CommandLine;\n' \
               '    if (-not [string]::IsNullOrWhiteSpace($history)) {\n' \
               '        $bleep = $(thebleep $args $history);\n' \
               '        if (-not [string]::IsNullOrWhiteSpace($bleep)) {\n' \
               '            if ($bleep.StartsWith("echo")) { $bleep = $bleep.Substring(5); }\n' \
               '            else { iex "$bleep"; }\n' \
               '        }\n' \
               '    }\n' \
               '    [Console]::ResetColor() \n' \
               '}\n'

    def app_alias_loader(self, alias_name):
        return ('function {name} {{\n'
                '    $env:TB_SHELL = "powershell";\n'
                '    iex "$(thebleep --alias {name})";\n'
                '    {name} @args;\n'
                '}}\n').format(name=alias_name)

    def and_(self, *commands):
        return u' -and '.join('({0})'.format(c) for c in commands)

    def how_to_configure(self):
        return ShellConfiguration(
            content=self.app_alias_loader(get_alias()),
            path='$profile',
            reload='. $profile',
            can_configure_automatically=False)

    def _get_version(self):
        """Returns the version of the current shell"""
        try:
            proc = Popen(
                ['powershell.exe', '$PSVersionTable.PSVersion'],
                stdout=PIPE,
                stderr=DEVNULL)
            version = proc.stdout.read().decode('utf-8').rstrip().split('\n')
            return '.'.join(version[-1].split())
        except IOError:
            proc = Popen(['pwsh', '--version'], stdout=PIPE, stderr=DEVNULL)
            return proc.stdout.read().decode('utf-8').split()[-1]
