from thebleep.utils import command_word_index, for_app, replace_argument


@for_app('brew', at_least=2)
def match(command):
    parts = command.script_parts
    start = command_word_index(parts)
    return (parts[start + 1] == 'update'
            and "Error: This command updates brew itself" in command.output
            and "Use `brew upgrade" in command.output)


def get_new_command(command):
    return replace_argument(command.script, 'update', 'upgrade')
