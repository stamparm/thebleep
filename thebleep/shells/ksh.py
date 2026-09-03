# -*- encoding: utf-8 -*-

"""The Korn shells: ksh93, mksh, and the pdksh that is OpenBSD's `ksh`.

One driver, because the three agree on everything an alias needs -- POSIX
aliases, functions and quoting, `fc` for the history, `$KSH_VERSION` for the
version -- and differ in what the driver looks up: which binary is running,
which startup file it reads, and how the history file is written.

  - ksh93 (AT&T, now ksh93u+m) reads `$ENV` when interactive, `~/.kshrc` by
    convention, and keeps `~/.sh_history`.
  - mksh reads `~/.mkshrc` and keeps history only where `HISTFILE` points.
  - OpenBSD's ksh reads `$ENV`, which the default `.profile` sets to
    `~/.kshrc`, and keeps history where `HISTFILE` points.

Every one of them writes the history file in its own binary framing rather
than as lines, so the driver reads the file as bytes and takes the commands
out of the framing; see `_get_history_lines`.

The ksh line editor has no way to hand a command back to the next prompt, so
editing before running is not offered, as for tcsh.

"""

import os
import re

from ..const import get_alias
from ..utils import memoize, tool_lines, tool_output, which
from .generic import Generic

# The names a Korn shell goes by, most usual first. `ksh` itself is whichever
# of them the system chose: a symlink to ksh93 or mksh on Linux, pdksh on
# OpenBSD, ksh93 on AIX and Solaris.
PROGRAMS = ('ksh', 'mksh', 'ksh93', 'oksh', 'lksh', 'pdksh')

# What separates entries in the history files. mksh frames each entry with
# `\0\xff\0\0\0` and a counter byte; ksh93 ends each with `\n\0`; both start
# with a header of bytes that are not text. Splitting on NUL and trimming
# what is not printable from each piece leaves the commands.
FRAMING = re.compile(u'^[\\x00-\\x1f\\x7f-\\x9f�]+|[\\x00-\\x1f\\x7f-\\x9f�]+$')


class Ksh(Generic):
    friendly_name = 'ksh'

    def __init__(self):
        self.program = self._program()
        # `mksh R59 ...` in `--version` and `--doctor`, not `ksh` for all three.
        self.friendly_name = self.program

    @staticmethod
    def _program():
        """Which Korn shell this is: the one the alias said, when it said one
        that is here, else the first of the usual names on PATH."""
        said = os.environ.get('TB_SHELL')
        if said in PROGRAMS and which(said):
            return said
        for name in PROGRAMS:
            if which(name):
                return name
        return 'ksh'

    def _shell_name(self):
        return self.program

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv([self.program, '-c', script])

    def app_alias(self, alias_name):
        # `fc -ln -1 -1` rather than `fc -ln -1`: ksh93 has already put the
        # alias's own line into the history by the time the alias runs, so a
        # range that ends at "now" ends with `bleep` itself, and the command
        # before it is what is wanted. Both ends given, both shells list the
        # one entry.
        return 'alias {0}={1}'.format(alias_name, self._in_single_quotes(
            'eval "$(TB_ALIAS={0} TB_SHELL={1} {2} "$(fc -ln -1 -1)")"'.format(
                alias_name, self.program, self._invocation())))

    def _parse_alias(self, line):
        """`name='value'` as ksh prints it, the quoting undone."""
        name, _, value = line.partition('=')
        if value.startswith("'") and value.endswith("'") and len(value) > 1:
            value = value[1:-1].replace("'\\''", "'")
        return name, value

    @memoize
    def get_aliases(self):
        # `-ic`, so that the user's startup file and its aliases are read; see
        # the note in `fish._get_functions` about the cost.
        return dict(
            self._parse_alias(line)
            for line in tool_lines([self.program, '-ic', 'alias'])
            if line and '=' in line and not line.startswith(' '))

    def _get_history_file_name(self):
        named = os.environ.get('HISTFILE')
        if named:
            return named
        home = os.path.expanduser('~')
        for candidate in ('.sh_history', '.mksh_history', '.ksh_history'):
            path = os.path.join(home, candidate)
            if os.path.isfile(path):
                return path
        return os.path.join(home, '.sh_history')

    def _get_history_lines(self):
        """The commands in a Korn shell history file.

        Read as bytes and split at NULs -- every framing the three shells use
        puts one between entries -- then decoded, dropping the bytes that are
        framing rather than text, and trimmed of what is not printable. A
        multi-line command stays one entry: ksh93 keeps its newlines and
        nothing here splits on them.

        """
        path = self._get_history_file_name()
        if not os.path.isfile(path):
            return
        try:
            with open(path, 'rb') as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - self.HISTORY_TAIL))
                data = handle.read()
        except OSError:
            return
        for piece in data.split(b'\x00'):
            text = FRAMING.sub(u'', piece.decode('utf-8', 'ignore')).strip()
            if text:
                yield text

    def _get_history_line(self, command_script):
        # Appended as text; the shell reads its own framing back leniently and
        # `history_limit` reads see the command through `_get_history_lines`.
        return u'{}\n'.format(command_script)

    def how_to_configure(self):
        # ksh93 and OpenBSD's ksh read `$ENV`, which is `~/.kshrc` wherever
        # anybody has set it up; mksh reads `~/.mkshrc` on its own. An
        # existing file of either name wins, then the shell's own default.
        home = os.path.expanduser('~')
        if os.environ.get('ENV'):
            config = os.environ['ENV'].replace(home, '~', 1)
        elif os.path.exists(os.path.join(home, '.mkshrc')):
            config = '~/.mkshrc'
        elif os.path.exists(os.path.join(home, '.kshrc')):
            config = '~/.kshrc'
        else:
            config = '~/.mkshrc' if self.program == 'mksh' else '~/.kshrc'
        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path=config,
            reload=self.program)

    def _get_version(self):
        """`$KSH_VERSION`, which every Korn shell sets: `Version AJM
        93u+m/1.0.10 2024-08-01`, `@(#)MIRBSD KSH R59 2025/04/26`, or
        `@(#)PD KSH v5.2.14 99/07/13.2` on OpenBSD."""
        return tool_output([self.program, '-c', 'echo "$KSH_VERSION"']
                           ).strip().replace('@(#)', '')
