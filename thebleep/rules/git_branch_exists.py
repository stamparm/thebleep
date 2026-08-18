import re
from thebleep.shells import shell
from thebleep.specific.git import git_support
from thebleep.utils import eager


@git_support
def match(command):
    return ("fatal: A branch named '" in command.output
            and "' already exists." in command.output)


@git_support
@eager
def get_new_command(command):
    branch_name = re.findall(
        r"fatal: A branch named '(.+)' already exists.", command.output)[0]
    # `shell.quote`, not a hand-rolled `\'`: a backslash does not escape
    # anything inside single quotes, and the name was not inside quotes at all.
    # git accepts a branch called `feature;rm -rf ~`, so this went to the shell
    # as two commands.
    branch = shell.quote(branch_name)
    for template in ([u'git branch -d {0}', u'git branch {0}'],
                     [u'git branch -d {0}', u'git checkout -b {0}'],
                     [u'git branch -D {0}', u'git branch {0}'],
                     [u'git branch -D {0}', u'git checkout -b {0}'],
                     [u'git checkout {0}']):
        yield shell.and_(*[part.format(branch) for part in template])
