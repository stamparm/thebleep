from ..conf import settings
from ..logs import warn
from ..shells import shell


def _get_alias(known_args):
    alias = shell.app_alias(known_args.alias)

    if known_args.enable_experimental_instant_mode:
        from ..utils import which

        if not which('script'):
            warn("Instant mode requires `script` app")
        else:
            return shell.instant_mode_alias(known_args.alias)

    return alias


def print_alias(known_args):
    settings.init(known_args)
    print(_get_alias(known_args))


def print_alias_loader(known_args):
    """Prints shell code that defines the alias the first time it is used.

    The alias itself is cheap to run but expensive to generate, and generating
    it starts a Python interpreter — at every shell startup, for everyone,
    whether or not they ever correct a command. This defers that to the first
    correction instead, which is the only moment it is needed.

    """
    settings.init(known_args)
    print(shell.app_alias_loader(known_args.alias_loader))
