import re
from thebleep.utils import for_app
from thebleep.specific.sudo import sudo_support
from thebleep.shells import shell


@sudo_support
@for_app('cd')
def match(command):
    # A generator rather than a tuple, and the output lowered once: a tuple's
    # elements are all evaluated before `any` sees any of them, so this lowered
    # the whole output three times and then looked at the first answer.
    output = command.output.lower()
    return command.script.startswith('cd ') and any(
        message in output
        for message in ('no such file or directory',
                        "cd: can't cd to",
                        'does not exist'))


@sudo_support
def get_new_command(command):
    # The backreference goes in unquoted, so the shell supplies only the
    # command word. Nushell's `mkdir` has no `-p`; see
    # `shells.generic.mkdir_command`.
    repl = shell.and_('{} \\1'.format(shell.mkdir_command()), 'cd \\1')
    return re.sub(r'^cd (.*)', repl, command.script)
