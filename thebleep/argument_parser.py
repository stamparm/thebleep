import sys
from .const import ARGUMENT_PLACEHOLDER, SHELLS, get_alias

# The defaults every parse starts from, and the flags the fast path below can
# account for on its own. Everything else means argparse gets the job.
DEFAULTS = {'alias': None,
            'alias_loader': None,
            'clear_cache': False,
            'command': [],
            'command_text': None,
            'debug': False,
            'doctor': False,
            'edit': False,
            'explain': False,
            'forget': None,
            'enable_experimental_instant_mode': False,
            'force_command': None,
            'help': False,
            'json': False,
            'pick': None,
            'repeat': False,
            'shell': None,
            'shell_logger': None,
            'stderr': None,
            'cwd': None,
            'version': False,
            'why': False,
            'yes': False}

SIMPLE_FLAGS = {'-y': 'yes',
                '--yes': 'yes',
                '--yeah': 'yes',
                '--hard': 'yes',
                '-r': 'repeat',
                '--repeat': 'repeat',
                '-e': 'edit',
                '--explain': 'explain',
                '--edit': 'edit',
                '-d': 'debug',
                '--debug': 'debug'}


class Arguments(object):
    """What argparse would have returned, without importing argparse."""

    def __init__(self, **values):
        self.__dict__.update(DEFAULTS)
        # `DEFAULTS['command']` is a list, so every `Arguments` built without
        # one shared the *same* list -- and anything appending to
        # `arguments.command` would have been appending to the default. Nothing
        # does today; a copy costs nothing and settles it.
        self.command = list(DEFAULTS['command'])
        self.__dict__.update(values)


def _fast_parse(arguments):
    """Parses the shapes the alias actually produces, or returns None.

    Correcting a command is the overwhelmingly common case and it only ever
    involves a command and a couple of switches. argparse costs more to import
    than the rest of a correction takes, so it is kept for the command lines
    that need it: `--help`, `--version`, anything taking a value, anything
    unrecognised, and anything contradictory.

    """
    values = {}
    for index, argument in enumerate(arguments):
        if argument == '--':
            command = arguments[index + 1:]
            if any(item == '--' for item in command):
                return None
            values['command'] = command
            break
        flag = SIMPLE_FLAGS.get(argument)
        if flag is None:
            return None
        if flag == 'yes' and values.get('repeat'):
            return None     # `-y` with `-r` is an error argparse must report
        if flag == 'repeat' and values.get('yes'):
            return None
        values[flag] = True

    return Arguments(**values)


class Parser(object):
    """Argument parser that can handle arguments with our special
    placeholder.

    """

    def __init__(self):
        self._parser = None

    def _build(self):
        """Builds the real parser, for the command lines that need one."""
        if self._parser is not None:
            return self._parser

        from argparse import ArgumentParser

        self._parser = ArgumentParser(prog='thebleep', add_help=False)
        self._add_arguments()
        return self._parser

    def _add_arguments(self):
        """Adds arguments to parser."""
        self._parser.add_argument(
            '-v', '--version',
            action='store_true',
            help="show program's version number and exit")
        self._parser.add_argument(
            '-a', '--alias',
            nargs='?',
            const=get_alias(),
            help='[custom-alias-name] prints alias for current shell')
        self._parser.add_argument(
            '--alias-loader',
            nargs='?',
            const=get_alias(),
            help='[custom-alias-name] prints shell code that defines the alias'
                 ' on first use, so shell startup costs nothing')
        self._parser.add_argument(
            '--shell',
            action='store',
            metavar='SHELL',
            help='the shell to act as, when working it out from the process'
                 ' tree gets it wrong: {}'.format(', '.join(sorted(SHELLS))))
        self._parser.add_argument(
            '--doctor',
            action='store_true',
            help='report what is installed and configured, and what is wrong')
        self._parser.add_argument(
            '--json',
            action='store_true',
            help='return structured suggestions without running a command')
        self._parser.add_argument(
            '--why',
            action='store_true',
            help='explain the previous failure, or return one with --json')
        self._parser.add_argument(
            '--pick',
            nargs='?',
            const=0,
            type=int,
            metavar='NUMBER',
            help='list recent failures, or select one by number')
        self._parser.add_argument(
            '--forget',
            action='store',
            type=int,
            metavar='NUMBER',
            help='remove one recorded failure')
        self._parser.add_argument(
            '--command',
            dest='command_text',
            metavar='COMMAND',
            help='use this exact command string with --json')
        self._parser.add_argument(
            '--stderr',
            action='store',
            metavar='FILE',
            help='read captured command output from FILE (or - for stdin)'
                 ' with --json')
        self._parser.add_argument(
            '--cwd',
            action='store',
            metavar='DIRECTORY',
            help='evaluate --json in DIRECTORY')
        self._parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='forget the compiled rules and the cached command lookups')
        self._parser.add_argument(
            '-l', '--shell-logger',
            action='store',
            help='log shell output to the file')
        self._parser.add_argument(
            '--enable-experimental-instant-mode',
            action='store_true',
            help='enable experimental instant mode, use on your own risk')
        self._parser.add_argument(
            '-h', '--help',
            action='store_true',
            help='show this help message and exit')
        self._parser.add_argument(
            '-e', '--edit',
            action='store_true',
            help='put the correction in your command line to edit'
                 ' instead of running it')
        self._parser.add_argument(
            '--explain',
            action='store_true',
            help='say which rule made each suggestion and what it matched')
        self._add_conflicting_arguments()
        self._parser.add_argument(
            '-d', '--debug',
            action='store_true',
            help='enable debug output')
        from argparse import SUPPRESS

        self._parser.add_argument(
            '--force-command',
            action='store',
            help=SUPPRESS)
        self._parser.add_argument(
            'command',
            nargs='*',
            help='command that should be fixed')

    def _add_conflicting_arguments(self):
        """It's too dangerous to use `-y` and `-r` together."""
        group = self._parser.add_mutually_exclusive_group()
        group.add_argument(
            '-y', '--yes', '--yeah', '--hard',
            action='store_true',
            help='execute fixed command without confirmation')
        group.add_argument(
            '-r', '--repeat',
            action='store_true',
            help='repeat on failure')

    def _prepare_arguments(self, argv):
        """Prepares arguments by:

        - removing placeholder and moving arguments after it to beginning,
          we need this to distinguish arguments from `command` with ours;

        - adding `--` before `command`, so our parse would ignore arguments
          of `command`.

        """
        if ARGUMENT_PLACEHOLDER in argv:
            index = argv.index(ARGUMENT_PLACEHOLDER)
            return argv[index + 1:] + ['--'] + argv[:index]
        elif argv and not argv[0].startswith('-') and argv[0] != '--':
            return ['--'] + argv
        else:
            return argv

    def parse(self, argv):
        arguments = self._prepare_arguments(argv[1:])
        fast = _fast_parse(arguments)
        if fast is not None:
            return fast
        return self._build().parse_args(arguments)

    def print_usage(self):
        self._build().print_usage(sys.stderr)

    def print_help(self):
        self._build().print_help(sys.stderr)
