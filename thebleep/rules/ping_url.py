# -*- encoding: utf-8 -*-

"""`ping` given a URL, which is the shape a browser hands you.

    $ ping https://github.com/
    ping: https://github.com/: Name or service not known

`ping` speaks to a host, not to a URL, and every part of the URL besides the
host is something it cannot use. Pasting one in from an address bar is how this
happens, so what is offered is the same command with the host on its own.

The host is taken apart with `urlsplit` rather than by trimming characters: a
URL can carry a user name, a password and a port, and `https://user@host:8443/x`
has to come out as `host`.

Refs: nvbn/thefuck#1243

"""

from thebleep.utils import for_app, replace_argument
from thebleep.shells import shell

# What a resolver says when it was handed something that is not a name. The
# first is GNU inetutils and iputils, the second is macOS and the BSDs.
NOT_A_HOST = ('name or service not known', 'unknown host',
              'cannot resolve', 'temporary failure in name resolution')

# What makes an argument a URL rather than a host: a scheme, or a path. A bare
# `github.com/` is the other half of the same mistake.
SCHEMES = ('http://', 'https://', 'ftp://', 'ftps://', 'ssh://', 'git://',
           'ws://', 'wss://')


def _looks_like_a_url(argument):
    lowered = argument.lower()
    return lowered.startswith(SCHEMES) or '/' in argument


def _urls(command):
    return [part for part in command.script_parts[1:]
            if not part.startswith('-') and _looks_like_a_url(part)]


@for_app('ping', 'ping6', at_least=1)
def match(command):
    # Lowered once into a variable, not once per message: the output can be a
    # megabyte, and copying it four times to ask four questions is four copies.
    lowered = command.output.lower()
    if not any(message in lowered for message in NOT_A_HOST):
        return False
    return bool(_hosts(command))


def _host(url):
    """The host in `url`, or `None` when there is not one to find."""
    from urllib.parse import urlsplit

    if not url.lower().startswith(SCHEMES):
        # `github.com/some/path` -- no scheme, so `urlsplit` would read the
        # whole thing as a path. Give it one to read.
        url = 'http://' + url

    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None

    return host or None


def _hosts(command):
    """The URLs to replace and what to replace them with.

    A URL only counts when it stands in the script as its own word. The words
    come from `shlex`, so one that was quoted -- `ping 'https://host/'` -- is
    not in the script under that spelling, `replace_argument` would not find it,
    and the suggestion would be the command back unchanged. Better not to offer
    one.

    """
    found = []
    padded = u' {} '.format(command.script)
    for url in _urls(command):
        host = _host(url)
        if not host or host == url:
            continue
        if u' {} '.format(url) not in padded:
            continue
        found.append((url, host))
    return found


def get_new_command(command):
    script = command.script
    for url, host in _hosts(command):
        # Quoted: the host comes out of something the user pasted, and this
        # goes back to the shell to be run.
        script = replace_argument(script, url, shell.quote(host))
    return script
