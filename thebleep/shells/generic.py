import io
import os
import shlex
from .. import const
from ..logs import warn
from ..utils import memoize
from ..conf import settings
from ..system import expanduser


class ShellConfiguration(object):
    """What to add to which file to make the alias survive a new shell.

    A `namedtuple` before, and nothing ever treated it as a tuple -- every use
    of it, here and in the tests, reads a field by name. `collections` is a
    seven-module import for `namedtuple` alone, and on Windows the number of
    modules a correction opens is most of what it costs, so the four fields are
    written out instead.

    """

    __slots__ = ('content', 'path', 'reload', 'can_configure_automatically')

    def __init__(self, content, path, reload, can_configure_automatically):
        self.content = content
        self.path = path
        self.reload = reload
        self.can_configure_automatically = can_configure_automatically

    def __eq__(self, other):
        if not isinstance(other, ShellConfiguration):
            return NotImplemented
        return all(getattr(self, name) == getattr(other, name)
                   for name in self.__slots__)

    def __repr__(self):
        return 'ShellConfiguration({})'.format(', '.join(
            '{}={!r}'.format(name, getattr(self, name))
            for name in self.__slots__))


# History windows to fall back through when the last ten entries are too big to
# hand to a program. Asking the shell for fewer entries keeps whole lines, which
# matters: half of a command must never be offered as something to run, and
# trimming a string down to a line boundary is not an option because both bash
# and zsh take seconds to do it -- `${h#*$'\n'}` over a 64K first line costs
# about 1.7s in bash 5.2 and about 12s in zsh 5.9.
TRANSPORT_WINDOWS = (2, 1)


def fit_transport():
    """Shell that cuts the transported shell state down to what will fit.

    The common case costs nothing: two builtin length tests that fail. Only a
    shell whose recent history really is enormous pays for another `fc`, and it
    is the case where a few milliseconds have stopped mattering.

    A window that still does not fit leaves the history empty, and an alias list
    that does not fit is dropped rather than trimmed -- half of an alias
    definition would expand a command into something the user never wrote.

    """
    steps = ['if [ ${{#TB_HISTORY}} -gt {limit} ]; then'
             ' TB_HISTORY=$(fc -ln -{window}); fi;'.format(
                 limit=const.TRANSPORT_LIMIT, window=window)
             for window in TRANSPORT_WINDOWS]
    steps.append('if [ ${{#TB_HISTORY}} -gt {limit} ]; then'
                 ' TB_HISTORY=; fi;'.format(limit=const.TRANSPORT_LIMIT))
    steps.append('if [ ${{#TB_SHELL_ALIASES}} -gt {limit} ]; then'
                 ' TB_SHELL_ALIASES=; fi;'.format(
                     limit=const.TRANSPORT_LIMIT))
    return ' '.join(steps)


def instant_log_path():
    """Where to keep the recording of a shell session, and under what name.

    `$XDG_RUNTIME_DIR` in preference to the temporary directory. What goes in
    this file is everything that scrolls past in a terminal for as long as the
    shell lives -- which is the contents of every file read, every token a
    command prints, and every password typed at a prompt that echoes. The
    runtime directory belongs to one user and is mode 0700; `/tmp` is shared,
    and the file used to be created there world-readable.

    The name still carries a UUID, because the directory may be shared and
    several shells may be recording at once.

    """
    # `tempfile` (which brings `shutil`, `random` and `bisect`) and `uuid`
    # (which brings `platform`) are imported here rather than at the top of the
    # module: only an instant-mode alias reaches this, and a correction was
    # paying to find and open seven modules for it.
    from tempfile import gettempdir
    from uuid import uuid4

    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if runtime and os.path.isdir(runtime):
        directory = runtime
    else:
        directory = gettempdir()

    return os.path.join(directory,
                        'thebleep-script-log-{}'.format(uuid4().hex))


class Generic(object):
    friendly_name = 'Generic Shell'

    def _shell_name(self):
        """The name the alias reports back in `TB_SHELL`."""
        return self.friendly_name.split()[0].lower()

    def get_aliases(self):
        return {}

    def _expand_aliases(self, command_script):
        aliases = self.get_aliases()
        binary = command_script.split(' ')[0]
        if binary in aliases:
            return command_script.replace(binary, aliases[binary], 1)
        else:
            return command_script

    def from_shell(self, command_script):
        """Prepares command before running in app."""
        return self._expand_aliases(command_script)

    def to_shell(self, command_script):
        """Prepares command for running in shell."""
        return command_script

    def _invocation(self):
        """The shell code an alias runs to reach The Bleep again.

        `thebleep` for an installed copy, and the interpreter and file of a
        checkout when this is one, so that a clone needs no install. See
        `thebleep.invocation`.

        The words are quoted by `self.quote`, so each shell applies its own
        rules -- a path with a space in it reaches PowerShell and Nushell as one
        word rather than as POSIX quoting they do not share.

        """
        from .. import invocation

        written = invocation.override()
        if written:
            return written

        words = invocation.parts()
        if words is None:
            return invocation.ENTRY_POINT

        return ' '.join(self.quote(word) for word in words)

    def app_alias(self, alias_name):
        return """alias {0}='eval "$(TB_ALIAS={0} """ \
               """{1} "$(fc -ln -1)")"'""".format(alias_name,
                                                  self._invocation())

    def app_alias_loader(self, alias_name):
        """Shell code defining `alias_name` as a stub that loads the real one.

        The stub redefines itself with the real alias and then hands the
        arguments over, so nothing but a function definition happens until the
        first correction.

        """
        # `TB_EXIT` first, and handed to the real alias explicitly.
        #
        # The stub's own `eval` is a command, so it replaces `$?` -- and the
        # real alias captures `$?` as its first act. So on the *first*
        # correction in a shell, the status it saw was the `eval`'s zero rather
        # than the failing command's, and a command that had just failed looked
        # like one that had worked. The user got `No bleeps given` the first
        # time and the right answer every time after, in the same shell, which
        # is a maddening thing to report.
        return ('{name}() {{\n'
                '    TB_EXIT=$?;\n'
                '    eval "$(TB_SHELL={shell} {command} --alias {name})";\n'
                '    TB_EXIT="$TB_EXIT" {name} "$@";\n'
                '}}').format(name=alias_name, shell=self._shell_name(),
                             command=self._invocation())

    def can_run_corrections(self):
        """Whether a correction can be handed back to this shell to be run.

        Every shell here but Nushell evaluates what we print. Nushell has no
        `eval` -- by design, because it parses a script through before running
        any of it -- so there a correction goes into the line editor and the
        user submits it themselves. See `shells.nushell`.

        """
        return True

    def can_edit_buffer(self):
        """Whether this shell can be handed a command to edit rather than run.

        Only shells with a documented way of writing their own line editor
        answer yes. There is no fallback for the ones that cannot: the trick
        that would work everywhere is pushing characters back into the
        terminal's input queue with `TIOCSTI`, which is injecting keystrokes
        into somebody's terminal from another process, and which Linux has
        been able to refuse since 5.17 for exactly that reason.

        """
        return False

    def edit_hint(self):
        """What to tell the user about where the correction went, or `None`.

        A shell that puts it straight into the line editor needs no
        explanation -- the correction is simply there, at the next prompt.

        """
        return None

    def _edit_line(self):
        """Shell code that acts on a correction the user asked to edit.

        It runs with the correction in `$TB_CMD`, in the alias, in the user's
        own shell -- which is the only place with a line editor to write to.

        """
        return ''

    def supports_instant_mode(self):
        """Whether this shell can have its output recorded as it scrolls past.

        Only the shells that override `instant_mode_alias` below; `--doctor`
        asks so it can say which case a user is in.

        """
        return False

    def instant_mode_alias(self, alias_name):
        warn("Instant mode not supported by your shell")
        return self.app_alias(alias_name)

    def _get_history_file_name(self):
        return ''

    def _get_history_line(self, command_script):
        return ''

    @memoize
    def get_history(self):
        return list(self._get_history_lines())

    def _get_history_lines(self):
        """Returns list of history entries."""
        history_file_name = self._get_history_file_name()
        if os.path.isfile(history_file_name):
            with io.open(history_file_name, 'r',
                         encoding='utf-8', errors='ignore') as history_file:

                lines = history_file.readlines()
                if settings.history_limit:
                    lines = lines[-settings.history_limit:]

                for line in lines:
                    prepared = self._script_from_history(line) \
                        .strip()
                    if prepared:
                        yield prepared

    def and_(self, *commands):
        return u' && '.join(commands)

    def or_(self, *commands):
        return u' || '.join(commands)

    def how_to_configure(self):
        return

    def split_command(self, command):
        """Split the command using shell-like syntax."""
        encoded = self.encode_utf8(command)

        try:
            splitted = [s.replace("??", "\\ ") for s in shlex.split(encoded.replace('\\ ', '??'))]
        except ValueError:
            splitted = encoded.split(' ')

        return self.decode_utf8(splitted)

    def encode_utf8(self, command):
        return command

    def decode_utf8(self, command_parts):
        return command_parts

    def mkdir_command(self):
        """How this shell spells "make a directory and its parents".

        Every POSIX shell runs the same `/bin/mkdir`, so `mkdir -p` is the
        answer almost everywhere. Nushell has a `mkdir` of its own with no such
        flag, which makes parents unconditionally -- so a suggestion containing
        `-p` did not parse there, and three of the commonest corrections
        (`cd` into a directory that does not exist, `touch` a file in one, `cp`
        into one) all produced code Nushell refused to run.

        Separate from `mkdir_p` because two rules build a template with a
        backreference in it rather than a path.

        """
        return u'mkdir -p'

    def mkdir_p(self, path):
        """`mkdir` for `path` and its parents, quoted."""
        return u'{} {}'.format(self.mkdir_command(), self.quote(path))

    def quote(self, s):
        """Return a shell-escaped version of the string s."""
        from shlex import quote

        return quote(s)

    def _script_from_history(self, line):
        return line

    def put_to_history(self, command):
        """Adds fixed command to shell history.

        In most of shells we change history on shell-level, but not
        all shells support it (Fish).

        """

    def get_builtin_commands(self):
        """Returns shells builtin commands."""
        return ['alias', 'bg', 'bind', 'break', 'builtin', 'case', 'cd',
                'command', 'compgen', 'complete', 'continue', 'declare',
                'dirs', 'disown', 'echo', 'enable', 'eval', 'exec', 'exit',
                'export', 'fc', 'fg', 'getopts', 'hash', 'help', 'history',
                'if', 'jobs', 'kill', 'let', 'local', 'logout', 'popd',
                'printf', 'pushd', 'pwd', 'read', 'readonly', 'return', 'set',
                'shift', 'shopt', 'source', 'suspend', 'test', 'times', 'trap',
                'type', 'typeset', 'ulimit', 'umask', 'unalias', 'unset',
                'until', 'wait', 'while']

    def _get_version(self):
        """Returns the version of the current shell"""
        return ''

    def unsupported_version(self):
        """Why this shell is too old to be supported, or `None` if it is not.

        Asked by `--doctor` and by the first-use message, and by nothing on the
        path a correction takes -- answering it means starting the shell to ask
        its version, which is most of the cost of a correction. A shell that
        needs a floor says so by overriding this.

        """
        return None

    def info(self):
        """Returns the name and version of the current shell"""
        try:
            version = self._get_version()
        except Exception as e:
            warn(u'Could not determine shell version: {}'.format(e))
            version = ''
        return u'{} {}'.format(self.friendly_name, version).rstrip()

    def _create_shell_configuration(self, content, path, reload):
        return ShellConfiguration(
            content=content,
            path=path,
            reload=reload,
            can_configure_automatically=expanduser(path).exists())
