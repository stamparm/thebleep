import re
from thebleep.shells import shell
from thebleep.utils import for_app


MISSING_DIRECTORY = re.compile(r"touch: (?:cannot touch ')?(.+)/.+'?:")


@for_app('touch')
def match(command):
    # A directory to create, not just the message: touch says the same thing
    # about a symlink whose target is missing, where there is no directory in
    # the name at all -- `touch: cannot touch 'brokenlink': No such file or
    # directory` -- and this used to match it and then raise IndexError.
    return ('No such file or directory' in command.output
            and MISSING_DIRECTORY.search(command.output) is not None)


def get_new_command(command):
    path = MISSING_DIRECTORY.search(command.output).group(1)
    return shell.and_(u'mkdir -p {}'.format(shell.quote(path)),
                      command.script)
