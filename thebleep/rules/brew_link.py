from thebleep.utils import for_app


@for_app('brew', at_least=2)
def match(command):
    # brew puts the formula between the flags now -- `brew link --overwrite
    # coreutils --dry-run` -- so only the part up to the formula is dependable.
    return (command.script_parts[1] in ['ln', 'link']
            and "brew link --overwrite" in command.output)


def get_new_command(command):
    command_parts = command.script_parts[:]
    command_parts[1] = 'link'
    command_parts.insert(2, '--overwrite')
    command_parts.insert(3, '--dry-run')
    return ' '.join(command_parts)
