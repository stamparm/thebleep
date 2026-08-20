from ..const import EXIT_EDIT, get_alias
from ..utils import DEVNULL, load_subprocess
from .generic import Generic, ShellConfiguration


# Bound the first time a process is started here; see `utils.load_subprocess`.
Popen = None
PIPE = None


class Powershell(Generic):
    friendly_name = 'PowerShell'

    def app_alias(self, alias_name):
        # `TB_SHELL` and `TB_ALIAS` are set for the call and put back
        # afterwards. They used to be set once by the loader and left in the
        # session's environment, where every later program saw them; and
        # `TB_ALIAS` was never set at all, so somebody who called the alias
        # something else got `bleep` in the history filtering and in `--repeat`.
        # Assigning $null to an $env: entry removes it, so a variable that was
        # not set comes back not set rather than as an empty one.
        #
        # The dropped branch was `if ($bleep.StartsWith("echo")) { $bleep =
        # $bleep.Substring(5) }`, which assigned and then did nothing with the
        # result: correcting `ehco test` to `echo test` silently did nothing.
        return ('function {name} {{\n'
                '    $history = (Get-History -Count 1).CommandLine;\n'
                '    if (-not [string]::IsNullOrWhiteSpace($history)) {{\n'
                '        $shell = $env:TB_SHELL;\n'
                '        $alias = $env:TB_ALIAS;\n'
                '        $edit = $env:TB_CAN_EDIT;\n'
                '        $env:TB_SHELL = "powershell";\n'
                '        $env:TB_ALIAS = "{name}";\n'
                '        $env:TB_CAN_EDIT = $(if (Get-Module PSReadLine)'
                ' {{ "1" }} else {{ $null }});\n'
                '        try {{\n'
                '            $bleep = $({command} $args $history);\n'
                '            $code = $LASTEXITCODE;\n'
                '        }} finally {{\n'
                '            $env:TB_SHELL = $shell;\n'
                '            $env:TB_ALIAS = $alias;\n'
                '            $env:TB_CAN_EDIT = $edit;\n'
                '        }}\n'
                '        if (-not [string]::IsNullOrWhiteSpace($bleep)) {{\n'
                '            if ($code -eq {exit_edit}) {{\n'
                '                [Microsoft.PowerShell.PSConsoleReadLine]'
                '::AddToHistory($bleep);\n'
                '            }} else {{\n'
                '                iex "$bleep";\n'
                '            }}\n'
                '        }}\n'
                '    }}\n'
                '    [Console]::ResetColor()\n'
                '}}\n').format(name=alias_name, exit_edit=EXIT_EDIT,
                               command=self._invocation())

    def can_edit_buffer(self):
        """As far as PSReadLine will go, which is not all the way.

        PSReadLine's editing API belongs to a key handler: outside one, the
        line it would write does not exist yet, and `Insert` called from a
        function at the prompt renders the text into the scrollback of a buffer
        that has already been submitted. Measured against PSReadLine 2.3.5 on
        PowerShell 7 -- `Insert` returns without complaint and the next prompt
        comes up empty.

        `AddToHistory` is the part that does work: the correction becomes the
        newest history entry, and one press of the up arrow brings it into the
        line editor to be edited. That is a keystroke more than the other
        shells need, which is why `edit_hint` says so.

        """
        return True

    def edit_hint(self):
        return 'Press the up arrow to edit it.'

    def app_alias_loader(self, alias_name):
        return ('function {name} {{\n'
                '    $shell = $env:TB_SHELL;\n'
                '    $env:TB_SHELL = "powershell";\n'
                '    try {{ iex "$({command} --alias {name})"; }}\n'
                '    finally {{ $env:TB_SHELL = $shell; }}\n'
                '    {name} @args;\n'
                '}}\n').format(name=alias_name,
                               command=self._invocation())

    def quote(self, s):
        """A PowerShell string literal for `s`.

        Not `shlex.quote`, which the generic shell uses. POSIX quoting escapes
        an embedded quote by leaving the single-quoted string and coming back
        into it -- `'a'"'"'b'` -- and PowerShell does not join adjacent string
        literals, so a command receives that as three arguments instead of as
        `a'b`. In PowerShell a single-quoted string is literal all the way
        through and an embedded quote is simply written twice.

        """
        return u"'{}'".format(s.replace(u"'", u"''"))

    def and_(self, *commands):
        """Runs each command only if the one before it succeeded.

        This used to be `(a) -and (b)`, which is not what `a && b` means.
        `-and` is a boolean operator over expressions and `$(...)` captures a
        command's output, so what it actually tests is whether the command
        *printed* anything. Measured against PowerShell 7.4:

            (exit 1) -and (mark)        mark did not run
            (exit 0, silent) -and (mark)    mark did not run
            (exit 0, printed) -and (mark)   mark ran

        So `git add . && git commit` skipped the commit, because `git add .`
        succeeds without saying anything.

        `&&` would do, but only from PowerShell 7. `$?` works there and in
        Windows PowerShell 5.1.

        """
        return self._chain(u'if ($?)', commands)

    def or_(self, *commands):
        """Runs each command only if the one before it failed.

        `||` is also PowerShell 7 and later only, and this is what `repeat`
        mode is built out of.

        """
        return self._chain(u'if (-not $?)', commands)

    def _chain(self, condition, commands):
        if not commands:
            return u''
        first, rest = commands[0], commands[1:]
        if not rest:
            return first
        return u'{}; {} {{ {} }}'.format(
            first, condition, self._chain(condition, rest))

    def how_to_configure(self):
        return ShellConfiguration(
            content=self.app_alias_loader(get_alias()),
            path='$profile',
            reload='. $profile',
            can_configure_automatically=False)

    def _get_version(self):
        """Returns the version of the current shell"""
        Popen, PIPE = load_subprocess(globals())
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
