import os
from thebleep.shells import shell
from thebleep.utils import command_word_index

# The forms a script can be run by, all of which are a path rather than a name
# the shell looks up on `PATH`:
#
#     ./deploy.sh          scripts/deploy.sh
#     ~/scripts/deploy.sh  /home/alice/scripts/deploy.sh
#
# Only `./` used to count, so the other three said "permission denied" and got
# no correction, which is the same mistake with the same fix.
#
# A bare `deploy.sh` with no separator in it is not one of them: that is a
# lookup on `PATH`, where "permission denied" is about a file somewhere else
# entirely and `chmod +x deploy.sh` would be about a file in this directory.
#
# Refs: nvbn/thefuck#1470


def _path(command):
    """The file the shell tried to run, as it was written, or `None`."""
    if not command.script_parts:
        return None

    start = command_word_index(command.script_parts)
    if start == len(command.script_parts):
        return None

    first = command.script_parts[start]
    if os.sep not in first and (os.altsep is None or os.altsep not in first):
        return None
    return first


def match(command):
    path = _path(command)
    if path is None or 'permission denied' not in command.output.lower():
        return False

    # `~` is the shell's to expand, and it had not expanded it when the words
    # were split -- so the question has to be asked about the expanded path
    # while the suggestion keeps the `~` the user typed.
    expanded = os.path.expanduser(path)
    return os.path.exists(expanded) and not os.access(expanded, os.X_OK)


def get_new_command(command):
    path = _path(command)

    # `./x` and `x` name the same file and `chmod` takes either; the `./` is
    # dropped because that is the shorter of the two and what this has always
    # written. Every other form is kept exactly as it was typed, so an absolute
    # path stays absolute and a `~` stays a `~` for the shell to expand.
    #
    # Quoted: `./my script` is a file somebody can have, and this goes back to
    # the shell to be run. A leading `~` stays outside the quotes, because
    # quoting it is what stops the shell expanding it.
    if path.startswith('./'):
        quoted = shell.quote(path[2:])
    elif path.startswith('~/'):
        quoted = u'~/{}'.format(shell.quote(path[2:]))
    else:
        quoted = shell.quote(path)

    return shell.and_(u'chmod +x {}'.format(quoted), command.script)
