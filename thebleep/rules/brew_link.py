from thebleep.utils import command_word_index, for_app, raw_script_parts


@for_app('brew', at_least=2)
def match(command):
    # brew puts the formula between the flags now -- `brew link --overwrite
    # coreutils --dry-run` -- so only the part up to the formula is dependable.
    parts = command.script_parts
    start = command_word_index(parts)
    return (parts[start + 1] in ['ln', 'link']
            and "brew link --overwrite" in command.output)


def get_new_command(command):
    command_parts = raw_script_parts(command.script)
    if len(command_parts) != len(command.script_parts):
        return []
    start = command_word_index(command_parts)
    command_parts[start + 1] = 'link'
    command_parts.insert(start + 2, '--overwrite')
    command_parts.insert(start + 3, '--dry-run')
    return ' '.join(command_parts)
