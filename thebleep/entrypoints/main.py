# Initialize output before importing any module, that can use colorama.
from ..system import init_output

init_output()

import os  # noqa: E402
import sys  # noqa: E402
from .. import logs  # noqa: E402
from ..argument_parser import Parser  # noqa: E402


def _main():
    # Each branch imports what it needs. Printing an alias has no business
    # loading the corrector, and it is the thing that runs at every shell
    # startup, so it is the one that must not pay for the rest.
    parser = Parser()
    known_args = parser.parse(sys.argv)

    if known_args.help:
        parser.print_help()
    elif known_args.version:
        from ..shells import shell
        from ..utils import get_installation_version

        logs.version(get_installation_version(),
                     sys.version.split()[0], shell.info())
    # It's important to check if an alias is being requested before checking if
    # `TB_HISTORY` is in `os.environ`, otherwise it might mess with subshells.
    # Check https://github.com/nvbn/thefuck/issues/921 for reference
    elif known_args.alias_loader:
        from .alias import print_alias_loader

        print_alias_loader(known_args)
    elif known_args.alias:
        from .alias import print_alias

        print_alias(known_args)
    elif known_args.command or 'TB_HISTORY' in os.environ:
        from .fix_command import fix_command

        fix_command(known_args)
    elif known_args.shell_logger:
        try:
            from .shell_logger import shell_logger  # noqa: E402
        except ImportError:
            logs.warn('Shell logger supports only Linux and macOS')
        else:
            shell_logger(known_args.shell_logger)
    else:
        parser.print_usage()


def main():
    try:
        _main()
    except BrokenPipeError:
        # Handle broken pipe gracefully (e.g., when terminal is closed)
        # Redirect remaining output to devnull to avoid additional errors
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(0)
