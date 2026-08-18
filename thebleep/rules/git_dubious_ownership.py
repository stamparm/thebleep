import re
from thebleep.shells import shell
from thebleep.specific.git import git_support

# git refuses to work in a repository owned by somebody else and prints the
# exact command that would allow it. Both the current wording, `detected
# dubious ownership in repository at`, and the older `unsafe repository` one
# end with this line, so reading it back is what catches either.
EXCEPTION = re.compile(
    r'^\s*git config --global --add safe\.directory (.+?)\s*$', re.MULTILINE)


@git_support
def match(command):
    return EXCEPTION.search(command.output) is not None


@git_support
def get_new_command(command):
    directory = EXCEPTION.search(command.output).group(1)

    # git prints the path unquoted, which does not survive a space in it.
    return shell.and_(
        u'git config --global --add safe.directory {}'.format(
            shell.quote(directory)),
        command.script)
