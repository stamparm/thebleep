patterns = ['you cannot perform this operation as root']


def match(command):
    if command.script_parts and command.script_parts[0] != 'sudo':
        return False

    output = command.output.lower()
    return any(pattern in output for pattern in patterns)


def get_new_command(command):
    return ' '.join(command.script_parts[1:])
