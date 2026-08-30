"""
The confusion in systemctl's param order is massive.
"""
from thebleep.specific.sudo import sudo_support
from thebleep.utils import for_app, raw_script_parts


@sudo_support
@for_app('systemctl')
def match(command):
    # Catches "Unknown operation 'service'." when executing systemctl with
    # misordered arguments
    cmd = command.script_parts
    return (cmd and 'Unknown operation \'' in command.output and
            len(cmd) - cmd.index('systemctl') == 3)


@sudo_support
def get_new_command(command):
    cmd = raw_script_parts(command.script)
    if len(cmd) != len(command.script_parts):
        return []
    cmd[-1], cmd[-2] = cmd[-2], cmd[-1]
    return ' '.join(cmd)
