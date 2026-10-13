import os
from thebleep.shells import shell
from thebleep.specific.sudo import sudo_support
from thebleep.utils import command_word_index, raw_script_parts


def _bare(word):
    """A name the shell looked up on PATH: no directory in it already."""
    return '/' not in word and (os.altsep is None or os.altsep not in word)


@sudo_support
def match(command):
    return (command.script_parts
            and command_word_index(command.script_parts)
            < len(command.script_parts)
            # `./script.sh` is a path already; fish says `Unknown command`
            # for that too, and this made it `././script.sh`.
            and _bare(command.script_parts[command_word_index(
                command.script_parts)])
            and os.path.exists(command.script_parts[command_word_index(
                command.script_parts)])
            # bash and zsh say `command not found`; fish `Unknown command:`.
            and ('command not found' in command.output
                 or 'unknown command' in command.output.lower()))


@sudo_support
def get_new_command(command):
    parts = raw_script_parts(command.script)
    start = command_word_index(parts)
    target = parts[start]
    fixed = command.script.replace(target, './' + target, 1)
    # `./script.sh` on a file nobody marked executable only trades `command not
    # found` for `permission denied`; the file needs the bit as well.
    if not os.access(command.script_parts[start], os.X_OK):
        return shell.and_(u'chmod +x {}'.format(shell.quote(target)), fixed)
    return fixed
