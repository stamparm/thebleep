import re

from ..const import EXIT_EDIT, get_alias
from ..utils import tool_lines, tool_output
from .generic import Generic, ShellConfiguration


# The characters that mean nothing special to PowerShell in an argument. The
# POSIX set, plus the backslash and colon of a Windows path.
BARE_WORD = re.compile(r'^[\w@%+=:,./\\-]+$')


class Powershell(Generic):
    friendly_name = 'PowerShell'
    dialect = 'powershell'

    def split_command(self, command):
        """Hide PowerShell's call operator from rule argument handling."""
        parts = super(Powershell, self).split_command(command)
        return parts[1:] if parts[:1] == ['&'] else parts

    def replay_argv(self, script):
        """See `Generic.replay_argv`.

        The mismatch was total here: a PowerShell command line handed to
        `Popen(shell=True)` on Windows goes through `cmd.exe`, which shares
        neither its syntax nor its cmdlets. `pwsh` first, because a machine
        that has PowerShell 7 is a machine that is using it.

        """
        from ..utils import which

        for interpreter in ('pwsh', 'powershell.exe', 'powershell'):
            if which(interpreter):
                return [interpreter, '-NoProfile', '-Command', script]

        return None

    def _invocation(self):
        """PowerShell needs `&` in front of a command it is given as a string.

        A statement that begins with a quoted string is a string *expression*
        there, not a command -- `'C:\\My Tools\\python.exe' x` evaluates the path
        and throws the rest away. The call operator is what makes it a command,
        and it is harmless in front of a bare name too.

        """
        written = super(Powershell, self)._invocation()
        return u'& ' + written if written.startswith(u"'") else written

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

    def inline_binding(self):
        """Esc Esc corrects the current line, through a PSReadLine key handler.

        The editing API that does not work from a function at the prompt
        (see `can_edit_buffer`) is the one that does work inside a key
        handler: `GetBufferState` reads the line and `Replace` rewrites it,
        which is exactly what PSReadLine's own sample profile does. The
        chord is two Escapes, as in the other shells.

        """
        return '''
Set-PSReadLineKeyHandler -Chord 'Escape,Escape' -BriefDescription 'TheBleepInline' -Description 'Correct the current line with The Bleep' -ScriptBlock {{
    $line = $null
    $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    if ([string]::IsNullOrWhiteSpace($line)) {{ return }}
    $shell = $env:TB_SHELL
    $env:TB_SHELL = 'powershell'
    try {{
        $fixed = ({command} --inline --command $line 2>$null | Out-String).TrimEnd()
        $code = $LASTEXITCODE
    }} finally {{
        $env:TB_SHELL = $shell
    }}
    if ($code -eq 0 -and -not [string]::IsNullOrWhiteSpace($fixed)) {{
        [Microsoft.PowerShell.PSConsoleReadLine]::Replace(0, $line.Length, $fixed)
    }}
}}
'''.format(command=self._invocation())

    def ambient_binding(self):
        """Return corrects a misspelled program before it runs.

        Enter is rebound to a handler that looks at the first word of the
        line: when `Get-Command` knows nothing by that name -- no cmdlet,
        function, alias or program -- the line is offered to The Bleep as a
        command-only correction, and a fix replaces the line so that return
        runs the corrected command. Anything else is `AcceptLine`, which is
        what return did before.

        """
        return '''
Set-PSReadLineKeyHandler -Key Enter -BriefDescription 'TheBleepAmbient' -Description 'Correct a misspelled program before it runs' -ScriptBlock {{
    $line = $null
    $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    $first = ($line.TrimStart() -split '\\s+', 2)[0]
    if (-not [string]::IsNullOrWhiteSpace($first) -and $first -notmatch '[\\\\/=$`"'']' -and -not (Get-Command -Name $first -ErrorAction SilentlyContinue)) {{
        $shell = $env:TB_SHELL
        $env:TB_SHELL = 'powershell'
        try {{
            $fixed = ({command} --inline --command $line 2>$null | Out-String).TrimEnd()
            $code = $LASTEXITCODE
        }} finally {{
            $env:TB_SHELL = $shell
        }}
        if ($code -eq 0 -and -not [string]::IsNullOrWhiteSpace($fixed) -and $fixed -ne $line) {{
            [Microsoft.PowerShell.PSConsoleReadLine]::Replace(0, $line.Length, $fixed)
            return
        }}
    }}
    [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
}}
'''.format(command=self._invocation())

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

        A word with nothing PowerShell would read specially in it is left as
        it is, the way `shlex.quote` leaves one: every correction goes through
        here, and `git 'push'` is not what anybody types.

        """
        if s and BARE_WORD.match(s):
            return s
        return self.literal(s)

    @staticmethod
    def literal(s):
        """A single-quoted PowerShell string, always quoted: for the places
        where a bare word would be read as a command rather than as text,
        such as the right-hand side of an assignment."""
        return u"'{}'".format(s.replace(u"'", u"''"))

    def put_on_path(self, directory):
        return u'$env:PATH = {} + [IO.Path]::PathSeparator + $env:PATH'.format(
            self.literal(directory))

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
        version = tool_lines(['powershell.exe', '$PSVersionTable.PSVersion'])
        if version:
            return '.'.join(version[-1].split())

        words = tool_output(['pwsh', '--version']).split()
        return words[-1] if words else ''
