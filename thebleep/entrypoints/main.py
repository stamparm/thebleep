# Initialize output before importing any module, that can use colorama.
from ..system import init_output

init_output()

import os  # noqa: E402
import sys  # noqa: E402
from .. import const, logs  # noqa: E402
from ..argument_parser import Parser  # noqa: E402


def _use_shell(name):
    """Honours `--shell`, by telling us what the alias normally would.

    `TB_SHELL` is how a shell introduces itself, so setting it is the whole
    implementation -- and it has to happen here, before anything imports
    `thebleep.shells`, because that package works out the shell as it is
    imported. Walking the process tree with psutil is both the expensive part
    and the part that gets the answer wrong in a container, an IDE terminal or
    under a wrapper script, which is what this flag is for.

    """
    if name not in const.SHELLS:
        logs.failed(u'Unknown shell {!r}. Known shells: {}.'.format(
            name, ', '.join(sorted(const.SHELLS))))
        sys.exit(2)
    os.environ['TB_SHELL'] = name


def _main():
    # Each branch imports what it needs. Printing an alias has no business
    # loading the corrector, and it is the thing that runs at every shell
    # startup, so it is the one that must not pay for the rest.
    parser = Parser()
    known_args = parser.parse(sys.argv)

    if known_args.shell:
        _use_shell(known_args.shell)

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
    elif known_args.doctor:
        from .doctor import doctor

        sys.exit(doctor())
    elif known_args.clear_cache:
        from .. import cachefile, rulepack

        rulepack.clear()
        cachefile.clear()
        print('Caches cleared. The next correction will be a slow one.')
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
