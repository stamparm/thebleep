import re
from thebleep.specific.nix import nix_available
from thebleep.shells import shell

regex = re.compile(r'nix-env -iA ([^\s]*)')
enabled_by_default = nix_available


def match(command):
    return regex.findall(command.output)


def get_new_command(command):
    name = regex.findall(command.output)[0]
    return shell.and_('nix-env -iA {}'.format(shell.quote(name)),
                      command.script)
