# -*- coding: utf-8 -*-

"""Each shell's `quote`, read back by that shell.

Names copied out of output and files go into suggestions through
`shell.quote`, and every shell reads quotes its own way: fish and xonsh take a
backslash inside single quotes as an escape, xonsh expands `$HOME` inside
them, PowerShell ends a single-quoted string at a curly quote. `shlex.quote`
was right for none of those, and each of them ran a payload. The oracle is
the shell itself: what it prints for the quoted word must be the word, and
the directory it ran in must still be empty.

Each shell that is not installed is skipped. In CI these run inside the
functional image, which has all of them, and PowerShell runs on every hosted
runner.

"""

import os
import shutil
import subprocess

import pytest

from thebleep import shells

PAYLOADS = [
    u'plain', u'a b', u"it's", u'\\', u'a\\', u"\\'", u"x'y'z", u'',
    u'build\\\'";touch pwned #', u"a\\' ' ; touch pwned #", u'$HOME', u'~',
    u'~/x', u'${HOME}', u'$(touch pwned)', u'`touch pwned`', u'(touch pwned)',
    u'@(1+1)', u'*', u'{a,b}', u'%self', u'-flag', u'a"b', u'a;b|c&d',
    u'a\\nb', u'a\tb', u'line\nbreak', u'é ü',
    u'build’; New-Item pwned; ’', u'a‘b‚c‛d',
]

# (driver, program, how to run a script file, how to print one argument)
SHELLS = [
    ('Bash', 'bash', ['bash'], u"printf '%s\\n' {}"),
    ('Zsh', 'zsh', ['zsh', '-f'], u"printf '%s\\n' {}"),
    ('Ksh', 'ksh', ['ksh'], u"printf '%s\\n' {}"),
    ('Tcsh', 'tcsh', ['tcsh', '-f'], u"printf '%s\\n' {}"),
    ('Fish', 'fish', ['fish', '--no-config'], u"printf '%s\\n' {}"),
    ('Xonsh', 'xonsh', ['xonsh', '--no-rc'], u"printf '%s\\n' {}"),
    ('Elvish', 'elvish', ['elvish'], u'echo {}'),
    ('Nushell', 'nu', ['nu'], u'print {}'),
    ('Powershell', 'pwsh', ['pwsh', '-NoProfile', '-File'],
     u'& {{ [Console]::Out.Write($args[0] + "`n") }} {}'),
]


@pytest.mark.parametrize('driver, program, argv, template', SHELLS,
                         ids=[entry[0] for entry in SHELLS])
def test_the_shell_reads_back_exactly_what_was_quoted(
        tmpdir, driver, program, argv, template):
    if not shutil.which(program):
        pytest.skip('{} is not installed'.format(program))
    shell = getattr(shells, driver)()
    payloads = PAYLOADS
    if driver == 'Tcsh':
        # tcsh has no way to quote a newline that `-c` will take; a payload
        # with one is a syntax error there, which runs nothing.
        payloads = [payload for payload in PAYLOADS if u'\n' not in payload]

    work = tmpdir.mkdir('work')
    script = tmpdir.join('script.' + ('ps1' if driver == 'Powershell' else 'sh'))
    script.write_text(u'\n'.join(
        template.format(shell.quote(payload)) for payload in payloads) + u'\n',
        encoding='utf-8')
    environment = dict(os.environ, HOME=str(work), LANG='C.UTF-8',
                       LC_ALL='C.UTF-8')
    environment.pop('XDG_CONFIG_HOME', None)
    result = subprocess.run(
        argv + [str(script)], cwd=str(work), env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=120)

    got = result.stdout.decode('utf-8', 'replace').replace(u'\r\n', u'\n')
    assert got == u''.join(payload + u'\n' for payload in payloads), \
        result.stderr.decode('utf-8', 'replace')
    assert [name for name in os.listdir(str(work))
            if not name.startswith('.')] == []
