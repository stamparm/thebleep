from thebleep.specific.sudo import sudo_support
from thebleep.utils import is_app

enabled_by_default = False


@sudo_support
def match(command):
    return (is_app(command, 'rm', at_least=1)
            and '/' in command.script_parts
            and '--no-preserve-root' not in command.script_parts
            and '--no-preserve-root' in command.output)


@sudo_support
def get_new_command(command):
    return u'{} --no-preserve-root'.format(command.script)
