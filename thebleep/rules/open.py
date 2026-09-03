# Opens URL's in the default web browser
#
# Example:
# > open github.com
# The file ~/github.com does not exist.
# Perhaps you meant 'http://github.com'?
#
import re

from thebleep.shells import shell
from thebleep.utils import eager, for_app

# A domain ends at the end of the word or at a slash; `config.server.json`
# contains `.se` and is a file, not a site.
DOMAIN = re.compile(r'^www\.|\.(?:com|edu|info|io|ly|me|net|org|se)(?:/|$)')


def is_arg_url(command):
    return any(DOMAIN.search(part) for part in command.script_parts[1:])


@for_app('open', 'xdg-open', 'gnome-open', 'kde-open')
def match(command):
    return (is_arg_url(command) or
            command.output.strip().startswith('The file ') and
            command.output.strip().endswith(' does not exist.'))


@eager
def get_new_command(command):
    output = command.output.strip()
    if is_arg_url(command):
        yield command.script.replace('open ', 'open http://')
    elif output.startswith('The file ') and output.endswith(' does not exist.'):
        # The argument as *typed*, quoting and all -- taken off the script
        # rather than out of `script_parts`, so whatever quoting made it a
        # single word for `open` still makes it a single word for `touch`.
        arg = command.script.split(' ', 1)[1]
        for option in ['touch', 'mkdir']:
            yield shell.and_(u'{} {}'.format(option, arg), command.script)
