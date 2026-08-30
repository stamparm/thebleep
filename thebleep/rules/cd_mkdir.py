from thebleep.utils import command_word_index, for_app, raw_script_parts
from thebleep.specific.sudo import sudo_support
from thebleep.shells import shell


@sudo_support
@for_app('cd')
def match(command):
    # A generator rather than a tuple, and the output lowered once: a tuple's
    # elements are all evaluated before `any` sees any of them, so this lowered
    # the whole output three times and then looked at the first answer.
    output = command.output.lower()
    start = command_word_index(command.script_parts)
    return (command.script_parts[start:start + 1] == ['cd']
            and len(command.script_parts) > start + 1 and any(
        message in output
        for message in ('no such file or directory',
                        "cd: can't cd to",
                        'does not exist')))


@sudo_support
def get_new_command(command):
    start = command_word_index(command.script_parts)
    raw_parts = raw_script_parts(command.script)
    if len(raw_parts) <= start + 1:
        return command.script

    # Keep the destination exactly as typed, including quotes. It is both a
    # path for mkdir and the original command's argument; rebuilding it from
    # parsed words would expose spaces and shell metacharacters.
    destination = ' '.join(raw_parts[start + 1:])
    mkdir = '{} {}'.format(shell.mkdir_command(), destination)
    return shell.and_(mkdir, command.script)
