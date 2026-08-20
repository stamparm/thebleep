import os
import sys
from . import logs
from .shells import shell
from .conf import settings, load_source
from .const import DEFAULT_PRIORITY, ALL_ENABLED
from .exceptions import EmptyCommand
from .utils import get_alias, format_raw_script
from .output_readers import get_output


class Command(object):
    """Command that should be fixed."""

    def __init__(self, script, output):
        """Initializes command with given values.

        :type script: basestring
        :type output: basestring

        """
        self.script = script
        self.output = output

    @property
    def stdout(self):
        logs.warn('`stdout` is deprecated, please use `output` instead')
        return self.output

    @property
    def stderr(self):
        logs.warn('`stderr` is deprecated, please use `output` instead')
        return self.output

    @property
    def script_parts(self):
        if not hasattr(self, '_script_parts'):
            try:
                self._script_parts = shell.split_command(self.script)
            except Exception:
                logs.debug(u"Can't split command script {} because:\n {}".format(
                    self, sys.exc_info()))
                self._script_parts = []

        return self._script_parts

    def __eq__(self, other):
        if isinstance(other, Command):
            return (self.script, self.output) == (other.script, other.output)
        else:
            return False

    def __hash__(self):
        # Hashable so that memoized rule helpers can key on the command
        # without pickling its entire output.
        return hash((self.script, self.output))

    def __repr__(self):
        return u'Command(script={}, output={})'.format(
            self.script, self.output)

    def update(self, **kwargs):
        """Returns new command with replaced fields.

        :rtype: Command

        """
        kwargs.setdefault('script', self.script)
        kwargs.setdefault('output', self.output)
        return Command(**kwargs)

    @classmethod
    def from_raw_script(cls, raw_script):
        """Creates instance of `Command` from a list of script parts.

        :type raw_script: [basestring]
        :rtype: Command
        :raises: EmptyCommand

        """
        script = format_raw_script(raw_script)
        if not script:
            raise EmptyCommand

        expanded = shell.from_shell(script)
        output = get_output(script, expanded)
        return cls(expanded, output)


class Rule(object):
    """Rule for fixing commands."""

    def __init__(self, name, match, get_new_command,
                 enabled_by_default, side_effect,
                 priority, requires_output, path=None):
        """Initializes rule with given fields.

        :type name: basestring
        :type match: (Command) -> bool
        :type get_new_command: (Command) -> (basestring | [basestring])
        :type enabled_by_default: boolean
        :type side_effect: (Command, basestring) -> None
        :type priority: int
        :type requires_output: bool
        :type path: basestring | None

        """
        self.name = name
        self.match = match
        self.get_new_command = get_new_command
        self.enabled_by_default = enabled_by_default
        self.side_effect = side_effect
        self.priority = priority
        self.requires_output = requires_output
        # Where the rule was loaded from. Only `--explain` reads it, to say
        # whether a suggestion came from a bundled rule, one of the user's own
        # or a third-party package -- so it is deliberately outside `__eq__`,
        # which is about what a rule does rather than where it lives.
        self.path = path

    def __eq__(self, other):
        if isinstance(other, Rule):
            return ((self.name, self.match, self.get_new_command,
                     self.enabled_by_default, self.side_effect,
                     self.priority, self.requires_output)
                    == (other.name, other.match, other.get_new_command,
                        other.enabled_by_default, other.side_effect,
                        other.priority, other.requires_output))
        else:
            return False

    def __repr__(self):
        return 'Rule(name={}, match={}, get_new_command={}, ' \
               'enabled_by_default={}, side_effect={}, ' \
               'priority={}, requires_output={})'.format(
                   self.name, self.match, self.get_new_command,
                   self.enabled_by_default, self.side_effect,
                   self.priority, self.requires_output)

    @classmethod
    def from_path(cls, path):
        """Creates rule instance from path.

        :type path: pathlib.Path | str
        :rtype: Rule

        """
        name = os.path.basename(str(path))[:-3]
        if name in settings.exclude_rules:
            logs.debug(u'Ignoring excluded rule: {}'.format(name))
            return
        with logs.debug_time(u'Importing rule: {};'.format(name)):
            try:
                # `from_module` is inside the try as well. A file in the rules
                # directory that imports fine but is not a rule -- somebody's
                # shared helper, half of a rule they are still writing -- used
                # to take the whole correction down with an AttributeError,
                # because only the import was guarded.
                return cls.from_module(name, load_source(name, str(path)))
            except Exception:
                logs.exception(u"Rule {} failed to load".format(name), sys.exc_info())
                return

    @classmethod
    def from_module(cls, name, rule_module):
        """Creates rule instance from an already executed rule module.

        :type name: basestring
        :rtype: Rule

        """
        priority = getattr(rule_module, 'priority', DEFAULT_PRIORITY)
        return cls(name, rule_module.match,
                   rule_module.get_new_command,
                   getattr(rule_module, 'enabled_by_default', True),
                   getattr(rule_module, 'side_effect', None),
                   settings.priority.get(name, priority),
                   getattr(rule_module, 'requires_output', True),
                   getattr(rule_module, '__file__', None))

    @property
    def is_enabled(self):
        """Returns `True` when rule enabled.

        :rtype: bool

        """
        return (
            self.name in settings.rules
            or self.enabled_by_default
            and ALL_ENABLED in settings.rules
        )

    def is_match(self, command):
        """Returns `True` if rule matches the command.

        :type command: Command
        :rtype: bool

        """
        if command.output is None and self.requires_output:
            return False

        try:
            with logs.debug_time(u'Trying rule: {};'.format(self.name)):
                if self.match(command):
                    return True
        except Exception:
            logs.rule_failed(self, sys.exc_info())

    def get_corrected_commands(self, command):
        """Returns generator with corrected commands.

        :type command: Command
        :rtype: Iterable[CorrectedCommand]

        """
        # One rule's parsing going wrong is that rule's problem, the same way it
        # already is in `is_match`. Without this it was everybody's: a rule that
        # matched and then raised while working out its suggestion took the whole
        # correction down with a traceback, including the suggestions every other
        # rule had produced.
        try:
            new_commands = self.get_new_command(command)
        except Exception:
            logs.rule_failed(self, sys.exc_info())
            return

        if not isinstance(new_commands, list):
            new_commands = (new_commands,)
        for n, new_command in enumerate(new_commands):
            # What a rule *returns* is as much its own business as what it
            # raises, and this is the boundary for both. Custom and third-party
            # rules are an advertised extension, and a rule with a path through
            # it that returns `None` -- a regex that matched in `match` and did
            # not match here, the commonest mistake there is -- used to reach
            # the display as `None.strip()` and take the whole CLI with it. A
            # broken rule should cost that rule.
            if not isinstance(new_command, str):
                if new_command is not None:
                    logs.debug(
                        u'Rule {} returned {}, which is not a command'.format(
                            self.name, type(new_command).__name__))
                continue

            yield CorrectedCommand(script=new_command,
                                   side_effect=self.side_effect,
                                   priority=(n + 1) * self.priority,
                                   rule=self)


class CorrectedCommand(object):
    """Corrected by rule command."""

    def __init__(self, script, side_effect, priority, rule=None):
        """Initializes instance with given fields.

        :type script: basestring
        :type side_effect: (Command, basestring) -> None
        :type priority: int
        :type rule: thebleep.types.Rule | None

        """
        self.script = script
        self.side_effect = side_effect
        self.priority = priority
        # Which rule suggested this, for `--explain`. Outside `__eq__` and
        # `__hash__` for the same reason `priority` is: two rules arriving at
        # the same command are one suggestion, and it is offered once.
        self.rule = rule

    def __eq__(self, other):
        """Ignores `priority` field."""
        if isinstance(other, CorrectedCommand):
            return (other.script, other.side_effect) == \
                   (self.script, self.side_effect)
        else:
            return False

    def __hash__(self):
        return (self.script, self.side_effect).__hash__()

    def __repr__(self):
        return u'CorrectedCommand(script={}, side_effect={}, priority={})'.format(
            self.script, self.side_effect, self.priority)

    def with_prefix(self, prefix):
        """The same correction with the wrapper it was found behind put back.

        :type prefix: str
        :rtype: CorrectedCommand

        """
        return CorrectedCommand(script=prefix + self.script,
                                side_effect=self.side_effect,
                                priority=self.priority,
                                rule=self.rule)

    def _get_script(self):
        """Returns fixed commands script.

        If `settings.repeat` is `True`, appends command with second attempt
        of running The Bleep in case fixed command fails again.

        """
        if settings.repeat:
            # The alias name is quoted too. It is validated where the alias is
            # printed, but it arrives here out of `TB_ALIAS` in the
            # environment, and this line goes back to the shell to be run.
            repeat_bleep = '{} --repeat {}--force-command {}'.format(
                shell.quote(get_alias()),
                '--debug ' if settings.debug else '',
                shell.quote(self.script))
            return shell.or_(self.script, repeat_bleep)
        else:
            return self.script

    def run(self, old_cmd):
        """Runs command from rule for passed command.

        :type old_cmd: Command

        """
        if self.side_effect:
            self.side_effect(old_cmd, self.script)
        if settings.alter_history:
            shell.put_to_history(self.script)

        sys.stdout.write(self._get_script())

    def edit(self):
        """Hands the script back to be edited rather than run.

        The script as the rule wrote it, and nothing else. `_get_script` is for
        a command about to be executed: in repeat mode it glues a second call to
        The Bleep onto the end, which is not something to put in front of
        somebody to edit.

        The side effect does not fire and the history is not touched either.
        Both belong to a command that ran, and this one has not -- the shell
        will record whatever the user finally submits from the line editor,
        which is the command they actually chose.

        """
        sys.stdout.write(self.script)
