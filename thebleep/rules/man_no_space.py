from thebleep.utils import command_word_index, replace_command_word


def match(command):
    start = command_word_index(command.script_parts)
    return (start < len(command.script_parts)
            and command.script_parts[start].startswith(u'man')
            and u'command not found' in command.output.lower())


def get_new_command(command):
    start = command_word_index(command.script_parts)
    if start == len(command.script_parts):
        return command.script

    command_word = command.script_parts[start]
    if not command_word.startswith(u'man'):
        return command.script

    return replace_command_word(
        command.script, start, u'man {}'.format(command_word[3:]))


priority = 2000
