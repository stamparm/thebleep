# -*- encoding: utf-8 -*-

"""`wp plugn list` -> `wp plugin list`, read out of WP-CLI's own answer.

WP-CLI is the command line of WordPress, and when a command is not registered
it names what was meant:

    $ wp plugn list
    Error: 'plugn' is not a registered wp command. See 'wp help' for
    available commands.
    Did you mean 'plugin'?

The wording is its own. It is not Symfony Console's `Command "x" is not
defined` -- which composer prints and `composer_not_command` reads -- so a
rule for one of them reads nothing for the other. Wordings captured from
wordpress:cli, WP-CLI 2.12.

"""

import re

from thebleep.shells import shell
from thebleep.utils import for_app, replace_argument


NOT_REGISTERED = re.compile(r"Error: '([^']+)' is not a registered wp command")
DID_YOU_MEAN = re.compile(r"Did you mean '([^']+)'\?")


@for_app('wp')
def match(command):
    broken = NOT_REGISTERED.search(command.output)
    suggested = DID_YOU_MEAN.search(command.output)
    return bool(broken and suggested)


def get_new_command(command):
    broken = NOT_REGISTERED.search(command.output).group(1)
    # Quoted: the name comes out of wp's output and the result of this goes
    # back to a shell to be evaluated.
    suggested = shell.quote(DID_YOU_MEAN.search(command.output).group(1))
    return replace_argument(command.script, broken, suggested)
