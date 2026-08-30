# -*- encoding: utf-8 -*-
from urllib.parse import urlparse
from thebleep.shells import shell
from thebleep.utils import command_word_index, for_app, raw_script_parts


def _target(command):
    parts = command.script_parts
    return parts[command_word_index(parts) + 1]


def _replace_target(command, target):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    parts[start + 1] = shell.quote(target)
    return ' '.join(parts)


@for_app('whois', at_least=1)
def match(command):
    """
    What the `whois` command returns depends on the 'Whois server' it contacted
    and is not consistent through different servers. But there can be only two
    types of errors I can think of with `whois`:
        - `whois https://en.wikipedia.org/` → `whois en.wikipedia.org`;
        - `whois en.wikipedia.org` → `whois wikipedia.org`.
    So we match any `whois` command and then:
        - if there is a slash: keep only the FQDN;
        - if there is no slash but there is a point: removes the left-most
          subdomain.

    We cannot either remove all subdomains because we cannot know which part is
    the subdomains and which is the domain, consider:
        - www.google.fr → subdomain: www, domain: 'google.fr';
        - google.co.uk → subdomain: None, domain; 'google.co.uk'.

    There has to be something to shorten, though. `whois localhost` has neither
    a slash nor a dot in it, and this used to match it and then hand back `None`
    as the correction, which is what the user was then shown.
    """
    target = _target(command)
    return '/' in target or '.' in target


def get_new_command(command):
    # Quoted: a host name is the user's own text, but it reaches the shell as a
    # command either way.
    url = _target(command)

    if '/' in url:
        return _replace_target(command, urlparse(url).netloc)

    path = urlparse(url).path.split('.')
    return [_replace_target(command, '.'.join(path[n:]))
            for n in range(1, len(path))]


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
