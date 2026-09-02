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
    elif getattr(known_args, 'forget', None) is not None:
        from .. import failure_store

        if failure_store.forget(known_args.forget):
            print('Forgot failure {}.'.format(known_args.forget))
        else:
            logs.failed('No recorded failure {}'.format(known_args.forget))
            sys.exit(2)
    elif getattr(known_args, 'learned', False):
        from .. import learning

        learning.print_entries()
    elif getattr(known_args, 'stats', None) is not None:
        from ..stats import print_report

        sys.exit(print_report(known_args.stats))
    elif getattr(known_args, 'learn_from_history', None) is not None:
        from .learn import learn_from_history

        sys.exit(learn_from_history(known_args))
    elif getattr(known_args, 'learn_last', None) is not None:
        from .. import learning

        entry = learning.learn_last(known_args.learn_last)
        if entry is None:
            logs.failed('No eligible correction to learn.')
            sys.exit(2)
        print('Learned {} -> {} ({}, {}).'.format(
            entry['before_parts'][entry['index']],
            entry['after_parts'][entry['index']], entry['scope'],
            entry['executable']))
    elif getattr(known_args, 'forget_learning', None) is not None:
        from .. import learning

        if learning.forget(known_args.forget_learning):
            print('Forgot learned correction {}.'.format(
                known_args.forget_learning))
        else:
            logs.failed('No learned correction {}'.format(
                known_args.forget_learning))
            sys.exit(2)
    elif known_args.alias_loader:
        from .alias import print_alias_loader

        print_alias_loader(known_args)
    elif known_args.alias:
        from .alias import print_alias

        print_alias(known_args)
    elif getattr(known_args, 'mcp', False):
        from ..mcp import serve

        sys.exit(serve())
    elif getattr(known_args, 'hook', None):
        from ..agent_hooks import print_config

        sys.exit(print_config(known_args.hook))
    elif getattr(known_args, 'as_hook', None):
        from ..conf import settings
        from ..agent_hooks import run

        settings.init(known_args)
        sys.exit(run(known_args.as_hook))
    # Before the correction branch, like `--doctor` and `--alias`, and for the
    # same reason: the alias exports `TB_HISTORY`, so from any shell that has
    # the alias loaded -- which is every shell anybody would start a logging
    # session from -- `bleep --shell-logger session.log` fell through to the
    # correction branch instead, and with `require_confirmation` off that
    # *executed* a suggestion.
    elif known_args.shell_logger:
        try:
            from .shell_logger import shell_logger  # noqa: E402
        except ImportError:
            logs.warn('Shell logger supports only Linux and macOS')
        else:
            shell_logger(known_args.shell_logger)
    elif known_args.json:
        from .json_output import json_output

        sys.exit(json_output(known_args))
    elif getattr(known_args, 'bind_inline', False):
        from .inline import print_binding

        sys.exit(print_binding(known_args))
    elif getattr(known_args, 'serve', False):
        from ..serve import main as serve_main

        sys.exit(serve_main(known_args))
    elif getattr(known_args, 'ambient', False):
        from .inline import print_ambient

        sys.exit(print_ambient(known_args))
    elif getattr(known_args, 'inline', False):
        from .inline import inline_command

        sys.exit(inline_command(known_args))
    elif known_args.command_text is not None:
        logs.failed('--command needs --json')
        sys.exit(2)
    elif known_args.why or getattr(known_args, 'pick', None) is not None:
        from .fix_command import fix_command

        fix_command(known_args)
    elif known_args.command or 'TB_HISTORY' in os.environ:
        from .fix_command import fix_command

        fix_command(known_args)
    else:
        parser.print_usage()


def main():
    try:
        _main()
    except BrokenPipeError:
        # Handle broken pipe gracefully (e.g., when terminal is closed)
        # Redirect remaining output to devnull to avoid additional errors
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull, sys.stdout.fileno())
        finally:
            os.close(devnull)
        sys.exit(0)
