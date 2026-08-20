import re
from thebleep.specific.apt import apt_available
from thebleep.utils import for_app

enabled_by_default = apt_available


@for_app('apt-get')
def match(command):
    return command.script.startswith('apt-get search')


def get_new_command(command):
    return re.sub(r'^apt-get', 'apt-cache', command.script)


# This rule never looks at what the command printed -- the command itself is
# the whole question -- so it does not need the output. Without saying so it was
# skipped whenever the output was not available, which is every correction where
# re-running the command was declined.
requires_output = False
