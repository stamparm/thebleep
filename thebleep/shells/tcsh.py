from time import time
import os
from ..const import get_alias
from ..utils import memoize, tool_lines, tool_output
from ..logs import warn
from .generic import Generic


class Tcsh(Generic):
    friendly_name = 'Tcsh'

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv(['tcsh', '-c', script])

    def _invocation(self):
        """What tcsh can be told to run, which is less than the others.

        A tcsh alias body is itself wrapped in single quotes, and there is no
        way to put a single quote inside one -- no `'"'"'` escape, no
        backslash. So an invocation that needs quoting cannot be written into a
        tcsh alias at all: the quote ends the body early and what is left fails
        with something that names neither the path nor the reason.

        A checkout under `~/My Projects/` is exactly that case. Rather than
        emit an alias that breaks, this says so and falls back to the installed
        command -- and `THEBLEEP_COMMAND`, used as written, is the way to say
        what tcsh should run instead.

        `Generic` has the same single-quoted body and does *not* need this,
        because POSIX shells can spell an embedded quote (`'\''`) and tcsh
        cannot. See `Generic._in_single_quotes`.

        """
        from .. import invocation

        written = super(Tcsh, self)._invocation()
        if "'" not in written:
            return written

        warn(
            u'Your checkout is at a path tcsh cannot put in an alias (a tcsh'
            u' alias is single-quoted and cannot contain a quote). The alias'
            u' will call `{}` instead. Set THEBLEEP_COMMAND to the command you'
            u' want it to run.'.format(invocation.ENTRY_POINT))
        return invocation.ENTRY_POINT

    def app_alias(self, alias_name):
        return ("alias {0} 'setenv TB_SHELL tcsh && setenv TB_ALIAS {0} && "
                "set bleeped_cmd=`history -h 2 | head -n 1` && "
                "eval `{1} ${{bleeped_cmd}}`'").format(
                    alias_name, self._invocation())

    def app_alias_loader(self, alias_name):
        """The eager alias, because tcsh cannot have a loader.

        Everywhere else the loader is a stub that replaces itself with the real
        alias on first use and then hands the arguments over. tcsh expands an
        alias when it *parses* the line, so the stub's call to itself is
        expanded before the `eval` that was meant to redefine it has run --
        and tcsh sees the alias referring to itself and says:

            RDY> bleep
            Alias loop.

        Every time, for as long as that line was in the `.cshrc`. It was the
        documented way to install for tcsh and it had never worked. Verified
        against tcsh 6.24.

        There is no way to write the stub that avoids this: the loop is the
        self-reference, and the point of a loader is the self-reference. So the
        flag gives tcsh the real alias instead, which works. What tcsh gives up
        is the loader\'s one advantage -- the body is written into the startup
        file rather than generated fresh, so after an upgrade that changes the
        body the line has to be regenerated.

        """
        return self.app_alias(alias_name)

    def _parse_alias(self, alias):
        name, value = alias.split("\t", 1)
        return name, value

    @memoize
    def get_aliases(self):
        # See the note in `fish._get_functions`: `tcsh -ic` reads the user's
        # `.cshrc`, and this is the hot path of every tcsh correction.
        return dict(
            self._parse_alias(alias)
            for alias in tool_lines(['tcsh', '-ic', 'alias'])
            if alias and '\t' in alias)

    def _get_history_file_name(self):
        return os.environ.get("HISTFILE",
                              os.path.expanduser('~/.history'))

    def _get_history_line(self, command_script):
        return u'#+{}\n{}\n'.format(int(time()), command_script)

    def how_to_configure(self):
        # tcsh reads `~/.tcshrc` if it is there and falls back to `~/.cshrc`,
        # which it shares with csh -- so that is the order here, and `~/.cshrc`
        # is what gets named on a machine with neither, because it is the one
        # csh would also read. The README and the installer said one each; this
        # is the shell's own rule and all three now follow it.
        home = os.path.expanduser('~')
        if os.path.exists(os.path.join(home, '.tcshrc')):
            config = '~/.tcshrc'
        else:
            config = '~/.cshrc'

        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path=config,
            reload='tcsh')

    def _get_version(self):
        """Returns the version of the current shell"""
        words = tool_output(['tcsh', '--version']).split()
        return words[1] if len(words) > 1 else ''
