# -*- encoding: utf-8 -*-

"""Elvish.

A shell with no aliases and no `&&`, a line editor that can be written to, and
a history kept in a database rather than a file. Verified against Elvish 0.21.

The alias is a function. It takes the previous command from
`edit:command-history` -- the newest entry is the function's own line, so the
one before it is what failed -- and runs The Bleep through `sh -c`, which is
how the exit status survives: Elvish turns a non-zero exit into an exception
that abandons the output capture, and the exit status is how The Bleep says
"edit this" rather than "run this". `sh` prints the status on the first line
and the correction after it.

`set edit:current-command` writes the line editor, so editing before running
is offered and the correction is simply there at the next prompt. Commands
are joined with `;`, because in Elvish a failing command throws and nothing
after it runs, which is what `&&` means elsewhere. Elvish has no aliases, so
there are none to expand; its history is in `~/.local/state/elvish/db.bolt`
and only the shell's daemon can read it, so none is read.

"""

import os
import re

from ..const import get_alias, EXIT_EDIT
from ..utils import tool_output
from .generic import Generic

# Elvish barewords: what can be an argument without quoting. `~` expands, `*`
# and `?` glob, `$` names a variable, `&` starts an option, so none of those.
BARE_WORD = re.compile(r'^[\w@%+=:,./-]+$')


class Elvish(Generic):
    friendly_name = 'Elvish'

    def replay_argv(self, script):
        """See `Generic.replay_argv`."""
        return self._posix_replay_argv(['elvish', '-c', script])

    def quote(self, s):
        """An Elvish string: bare when it can be, single-quoted otherwise,
        with an embedded quote written twice, which is Elvish's own rule."""
        if s and BARE_WORD.match(s):
            return s
        return u"'{}'".format(s.replace(u"'", u"''"))

    def app_alias(self, alias_name):
        return (
            'use str\n'
            'fn {name} {{|@args|\n'
            '  var prev = [(edit:command-history &newest-first '
            '| take 2 | drop 1)][0][cmd]\n'
            '  var out = (env TB_SHELL=elvish TB_ALIAS={name} TB_CAN_EDIT=1 '
            "sh -c 'fixed=$(\"$@\"); printf \"%s\\n%s\" \"$?\" \"$fixed\"' "
            'sh {command} $prev | slurp)\n'
            '  var status fixed = (str:split &max=2 "\\n" $out)\n'
            '  if (eq $status {edit}) {{\n'
            '    {edit_line}\n'
            "  }} elif (not-eq $fixed '') {{\n"
            '    eval $fixed\n'
            '  }}\n'
            '}}').format(name=alias_name, command=self._invocation(),
                         edit=EXIT_EDIT, edit_line=self._edit_line())

    def app_alias_loader(self, alias_name):
        # A function definition is already what a stub would be.
        return self.app_alias(alias_name)

    def can_edit_buffer(self):
        return True

    def _edit_line(self):
        """`edit:current-command` is the line editor's buffer; set from a
        command, it is what the next prompt opens with."""
        return 'set edit:current-command = $fixed'

    def and_(self, *commands):
        # A failing command throws and the rest of the code does not run:
        # `;` is Elvish's `&&`.
        return u'; '.join(commands)

    def or_(self, *commands):
        if len(commands) == 1:
            return commands[0]
        return u'try {{ {} }} catch {{ {} }}'.format(
            commands[0], self.or_(*commands[1:]))

    def put_on_path(self, directory):
        return u'set paths = [{} $@paths]'.format(self.quote(directory))

    def get_aliases(self):
        # Elvish has functions, not aliases, and no way to ask for them from
        # outside the interactive shell.
        return {}

    def how_to_configure(self):
        # Written with forward slashes on every platform: this is a line for
        # a person to read, not a path for `open`.
        base = os.environ.get('XDG_CONFIG_HOME')
        if base:
            config = base.replace(os.path.expanduser('~'), '~', 1).replace(
                '\\', '/') + '/elvish/rc.elv'
        else:
            config = '~/.config/elvish/rc.elv'
        return self._create_shell_configuration(
            content=self.app_alias_loader(get_alias()),
            path=config,
            reload='elvish')

    def _get_version(self):
        """`0.21.0+Debian-2+b7`, as `elvish -version` prints it."""
        return tool_output(['elvish', '-version']).strip()
