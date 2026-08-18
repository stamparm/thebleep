import re
from thebleep.shells import shell


patterns = (
    r"mv: cannot move '[^']*' to '([^']*)': No such file or directory",
    r"mv: cannot move '[^']*' to '([^']*)': Not a directory",
    r"cp: cannot create regular file '([^']*)': No such file or directory",
    r"cp: cannot create regular file '([^']*)': Not a directory",
)


def match(command):
    for pattern in patterns:
        if re.search(pattern, command.output):
            return True

    return False


def get_new_command(command):
    for pattern in patterns:
        file = re.findall(pattern, command.output)

        if file:
            file = file[0]
            dir = file[0:file.rfind('/')]

            return shell.and_(u'mkdir -p {}'.format(shell.quote(dir)),
                              command.script)
