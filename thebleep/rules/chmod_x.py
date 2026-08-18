import os
from thebleep.shells import shell


def match(command):
    return (command.script.startswith('./')
            and 'permission denied' in command.output.lower()
            and os.path.exists(command.script_parts[0])
            and not os.access(command.script_parts[0], os.X_OK))


def get_new_command(command):
    # Quoted: `./my script` is a file somebody can have, and this goes back to
    # the shell to be run.
    return shell.and_(
        u'chmod +x {}'.format(shell.quote(command.script_parts[0][2:])),
        command.script)
