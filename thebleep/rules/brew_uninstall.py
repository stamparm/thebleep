from thebleep.utils import command_word_index, for_app, raw_script_parts


@for_app('brew', at_least=2)
def match(command):
    parts = command.script_parts
    start = command_word_index(parts)
    return (parts[start + 1] in ['uninstall', 'rm', 'remove']
            and "brew uninstall --force" in command.output)


def get_new_command(command):
    command_parts = raw_script_parts(command.script)
    if len(command_parts) != len(command.script_parts):
        return []
    start = command_word_index(command_parts)
    command_parts[start + 1] = 'uninstall'
    command_parts.insert(start + 2, '--force')
    return ' '.join(command_parts)
