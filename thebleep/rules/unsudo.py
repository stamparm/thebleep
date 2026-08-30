patterns = ['you cannot perform this operation as root']


def match(command):
    parts = command.script_parts
    if (len(parts) < 2 or parts[0] != 'sudo'
            or parts[1].startswith('-')):
        return False

    output = command.output.lower()
    return any(pattern in output for pattern in patterns)


def get_new_command(command):
    # Preserve quoting in the command being unwrapped: `sudo echo 'a;...'`
    # contains one literal argument, and rebuilding it from parsed words would
    # expose the semicolon to the shell.
    parts = command.script_parts
    if len(parts) < 2 or parts[0] != 'sudo' or parts[1].startswith('-'):
        return command.script

    parts = command.script.split(None, 1)
    return parts[1] if len(parts) > 1 else ''
